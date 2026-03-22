import asyncio
import json
import logging

import anthropic
from asgiref.sync import sync_to_async
from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .context_builder import ContextBuilder, extract_structured_data, merge_profile_data
from .models import Conversation, Message, UserProfile, SkillTaster
from .serializers import ChatSendSerializer

logger = logging.getLogger(__name__)


class ChatSendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChatSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        conversation_id = data.get("conversation_id")

        if conversation_id:
            try:
                conversation = Conversation.objects.get(
                    id=conversation_id, user=request.user
                )
            except Conversation.DoesNotExist:
                return Response(
                    {"detail": "Conversation not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            conversation = Conversation.objects.create(
                user=request.user,
                conversation_type=data["conversation_type"],
                metadata=data.get("metadata", {}),
            )

        message = Message.objects.create(
            conversation=conversation,
            role="user",
            content=data["message"],
        )

        return Response(
            {
                "conversation_id": str(conversation.id),
                "message_id": str(message.id),
            },
            status=status.HTTP_201_CREATED,
        )


async def chat_stream_view(request, conversation_id):
    """SSE stream of Claude's response for a conversation."""
    # Authenticate via cookie
    from api.authentication import CookieJWTAuthentication

    auth = CookieJWTAuthentication()
    try:
        result = await sync_to_async(auth.authenticate)(request)
        if result is None:
            return StreamingHttpResponse(
                _error_event("Authentication required."),
                content_type="text/event-stream",
                status=401,
            )
        user, _ = result
    except Exception:
        return StreamingHttpResponse(
            _error_event("Authentication failed."),
            content_type="text/event-stream",
            status=401,
        )

    try:
        conversation = await Conversation.objects.aget(
            id=conversation_id, user=user
        )
    except Conversation.DoesNotExist:
        return StreamingHttpResponse(
            _error_event("Conversation not found."),
            content_type="text/event-stream",
            status=404,
        )

    profile = await UserProfile.objects.aget(user=user)

    # Summarize if needed (>20 messages and no summary yet)
    message_count = await conversation.messages.acount()
    if message_count > 20 and not conversation.summary:
        await _summarize_conversation(conversation)

    # Build context
    builder = ContextBuilder()
    messages_qs = conversation.messages.all()

    if conversation.conversation_type == "onboarding":
        system_prompt, conv_messages = await builder.build_for_onboarding(
            profile, messages_qs, summary=conversation.summary
        )
    elif conversation.conversation_type == "skill_taster":
        taster_id = (conversation.metadata or {}).get("taster_id")
        module_id = (conversation.metadata or {}).get("module_id")
        if taster_id:
            try:
                taster = await SkillTaster.objects.select_related("career_path").aget(
                    id=taster_id, user=user
                )
                system_prompt, conv_messages = await builder.build_for_taster_help(
                    profile, messages_qs, taster, module_id, summary=conversation.summary
                )
            except SkillTaster.DoesNotExist:
                system_prompt, conv_messages = await builder.build_for_onboarding(
                    profile, messages_qs, summary=conversation.summary
                )
        else:
            system_prompt, conv_messages = await builder.build_for_onboarding(
                profile, messages_qs, summary=conversation.summary
            )
    else:
        system_prompt, conv_messages = await builder.build_for_onboarding(
            profile, messages_qs, summary=conversation.summary
        )

    HEARTBEAT_INTERVAL = 15  # seconds
    SENTINEL = object()

    async def event_stream():
        full_response = ""
        hit_tag = False
        queue = asyncio.Queue()

        async def heartbeat():
            """Send keepalive comments to prevent proxy/browser timeouts."""
            try:
                while True:
                    await asyncio.sleep(HEARTBEAT_INTERVAL)
                    await queue.put(": keepalive\n\n")
            except asyncio.CancelledError:
                pass

        async def claude_stream():
            """Stream tokens from Claude, buffering potential XML tags."""
            nonlocal full_response, hit_tag
            TAGS = ["<profile_update>", "<ui_widget>"]
            try:
                client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
                pending = ""  # Buffer for text that might be a tag start

                async with client.messages.stream(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2000,
                    system=system_prompt,
                    messages=conv_messages,
                ) as stream:
                    async for text in stream.text_stream:
                        full_response += text
                        if hit_tag:
                            continue

                        pending += text

                        # Check if buffer contains a complete tag
                        found_tag = False
                        for tag in TAGS:
                            idx = pending.find(tag)
                            if idx != -1:
                                hit_tag = True
                                found_tag = True
                                # Send any clean text BEFORE the tag
                                before = pending[:idx].rstrip("\n")
                                if before:
                                    await queue.put(
                                        f"data: {json.dumps({'type': 'token', 'data': before})}\n\n"
                                    )
                                pending = ""
                                break

                        if found_tag or hit_tag:
                            continue

                        # Check if the end of pending could be the START of a tag
                        might_be_tag = False
                        for tag in TAGS:
                            for k in range(1, len(tag)):
                                if pending.endswith(tag[:k]):
                                    might_be_tag = True
                                    break
                            if might_be_tag:
                                break

                        if might_be_tag:
                            # Send everything BEFORE the last '<' (safe), keep the rest
                            last_lt = pending.rfind("<")
                            if last_lt > 0:
                                safe = pending[:last_lt]
                                await queue.put(
                                    f"data: {json.dumps({'type': 'token', 'data': safe})}\n\n"
                                )
                                pending = pending[last_lt:]
                        else:
                            # No tag possible — flush entire buffer
                            await queue.put(
                                f"data: {json.dumps({'type': 'token', 'data': pending})}\n\n"
                            )
                            pending = ""

                # Stream ended — flush any remaining non-tag text
                if pending and not hit_tag:
                    await queue.put(
                        f"data: {json.dumps({'type': 'token', 'data': pending})}\n\n"
                    )

            except Exception as e:
                logger.exception("Claude API error")
                await queue.put(
                    f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"
                )
            finally:
                await queue.put(SENTINEL)

        heartbeat_task = asyncio.create_task(heartbeat())
        claude_task = asyncio.create_task(claude_stream())

        try:
            while True:
                item = await queue.get()
                if item is SENTINEL:
                    break
                yield item
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        # Wait for claude_task to fully finish (should already be done)
        await claude_task

        # Extract structured data and save
        clean_text, profile_update, widget_spec = extract_structured_data(full_response)

        # Save assistant message with clean text
        assistant_msg = await Message.objects.acreate(
            conversation=conversation,
            role="assistant",
            content=clean_text,
            metadata={"profile_update": profile_update} if profile_update else {},
        )

        # Update profile if we got structured data
        done_data = {"message_id": str(assistant_msg.id)}

        if profile_update:
            onboarding_completed = profile_update.pop("onboarding_completed", None)

            profile.profile_data = merge_profile_data(
                profile.profile_data or {}, profile_update
            )
            profile.profile_version += 1

            if onboarding_completed:
                profile.onboarding_completed = True
                profile.journey_stage = "career_discovery"

            await profile.asave()
            done_data["profile_update"] = profile.profile_data
            done_data["onboarding_completed"] = profile.onboarding_completed
            done_data["journey_stage"] = profile.journey_stage

        if widget_spec:
            done_data["widget"] = widget_spec

        yield f"data: {json.dumps({'type': 'done', 'data': done_data})}\n\n"

    response = StreamingHttpResponse(
        event_stream(), content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


async def _summarize_conversation(conversation):
    """Generate a summary for conversations with >20 messages."""
    messages = []
    async for msg in conversation.messages.all().order_by("created_at")[:20]:
        messages.append(f"{msg.role}: {msg.content}")

    messages_text = "\n".join(messages)

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system="Summarize this conversation in 2-3 sentences, preserving key facts and decisions.",
            messages=[{"role": "user", "content": messages_text}],
        )
        conversation.summary = response.content[0].text
        await conversation.asave()
    except Exception:
        logger.exception("Failed to summarize conversation")


def _error_event(message):
    """Yield a single SSE error event."""
    yield f"data: {json.dumps({'type': 'error', 'data': message})}\n\n"
