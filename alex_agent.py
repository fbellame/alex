from typing import Any
from dotenv import load_dotenv
import logging
from dataclasses import dataclass, field
from typing import Annotated, Optional
from pydantic import Field
import time
import yaml
import asyncio
import argparse
import sys
from datetime import datetime, timezone

from livekit import agents, api
from livekit.agents import AgentSession, Agent, RoomInputOptions, function_tool, RunContext, metrics, JobContext, JobProcess
from livekit.plugins import (
    openai,
    deepgram,
    noise_cancellation,
    silero,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.agents.voice import MetricsCollectedEvent

# Import our optimized database manager
from db_manager import AsyncDatabaseManager, OptimizedMetricsCollector, InMemoryMetrics

logger = logging.getLogger("dental_assistant")
logger.setLevel(logging.INFO)

@dataclass
class UserData:
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    booking_date_time: Optional[str] = None
    booking_reason: Optional[str] = None
    
    agents: dict[str, Agent] = field(default_factory=dict)
    prev_agent: Optional[Agent] = None
    
    # Database integration
    session_id: Optional[str] = None
    db_manager: Optional[AsyncDatabaseManager] = None
    session_start_time: Optional[float] = None
    metrics_collector: Optional[OptimizedMetricsCollector] = None
    in_memory_metrics: InMemoryMetrics = field(default_factory=InMemoryMetrics)
    
    # Recording settings
    enable_recording: bool = False

    def summarize(self) -> str:
        data = {
            "customer_name": self.customer_name or "unknown",
            "customer_phone": self.customer_phone or "unknown",
            "booking_date_time": self.booking_date_time or "unknown",
            "booking_reason": self.booking_reason or "unknown",
        }
        return yaml.dump(data)
    
    def save_to_db(self):
        """Save current user data to database (non-blocking)"""
        if self.db_manager and self.session_id:
            self.db_manager.queue_user_data(self.session_id, self)


RunContext_T = RunContext[UserData]

load_dotenv()

# Optimized function tools with minimal logging
@function_tool()
async def update_name(
    name: Annotated[str, Field(description="The customer's name")],
    context: RunContext_T,
) -> str:
    """Called when the user provides their name.
    Confirm the spelling with the user before calling the function."""
    userdata = context.userdata
    userdata.customer_name = name
    userdata.save_to_db()  # Non-blocking save
    
    # Update in-memory metrics
    userdata.in_memory_metrics.update("customer_name_updated", 1)
    
    # Lightweight logging
    if userdata.enable_recording and userdata.db_manager and userdata.session_id:
        userdata.db_manager.queue_transcript(
            userdata.session_id,
            context.session.current_agent.__class__.__name__,
            "function_call",
            f"Updated name: {name}",
            metadata={"function": "update_name"}
        )
    
    return f"The name is updated to {name}"

@function_tool()
async def update_phone(
    phone: Annotated[str, Field(description="The customer's phone number")],
    context: RunContext_T,
) -> str:
    """Called when the user provides their phone number.
    Confirm the spelling with the user before calling the function."""
    userdata = context.userdata
    userdata.customer_phone = phone
    userdata.save_to_db()  # Non-blocking save
    
    # Update in-memory metrics
    userdata.in_memory_metrics.update("customer_phone_updated", 1)
    
    # Lightweight logging
    if userdata.enable_recording and userdata.db_manager and userdata.session_id:
        userdata.db_manager.queue_transcript(
            userdata.session_id,
            context.session.current_agent.__class__.__name__,
            "function_call",
            f"Updated phone: {phone}",
            metadata={"function": "update_phone"}
        )
    
    return f"The phone number is updated to {phone}"

@function_tool()
async def update_booking_date_time(
    date_time: Annotated[str, Field(description="The booking date and time")],
    context: RunContext_T
) -> str:
    """Called when the user provides their booking date and time.
    Confirm the spelling with the user before calling the function."""
    userdata = context.userdata
    userdata.booking_date_time = date_time
    userdata.save_to_db()  # Non-blocking save
    
    # Update in-memory metrics
    userdata.in_memory_metrics.update("booking_datetime_updated", 1)
    
    # Lightweight logging
    if userdata.enable_recording and userdata.db_manager and userdata.session_id:
        userdata.db_manager.queue_transcript(
            userdata.session_id,
            context.session.current_agent.__class__.__name__,
            "function_call",
            f"Updated booking: {date_time}",
            metadata={"function": "update_booking_date_time"}
        )
    
    return f"The booking date and time is updated to {date_time}"

@function_tool()
async def update_booking_reason(
    reason: Annotated[str, Field(description="The booking reason")],
    context: RunContext_T
) -> str:
    """Called when the user provides their booking reason.
    Confirm the spelling with the user before calling the function."""
    userdata = context.userdata
    userdata.booking_reason = reason
    userdata.save_to_db()  # Non-blocking save
    
    # Update in-memory metrics
    userdata.in_memory_metrics.update("booking_reason_updated", 1)
    
    # Lightweight logging
    if userdata.enable_recording and userdata.db_manager and userdata.session_id:
        userdata.db_manager.queue_transcript(
            userdata.session_id,
            context.session.current_agent.__class__.__name__,
            "function_call",
            f"Updated reason: {reason}",
            metadata={"function": "update_booking_reason"}
        )
    
    return f"The booking reason is updated to {reason}"

@function_tool()
async def get_current_datetime(context: RunContext_T) -> str:
    """Get the current date and time."""
    current_time = datetime.now(timezone.utc)
    # Convert to Montreal timezone (EST/EDT)
    montreal_time = current_time.astimezone()
    return f"Current date and time: {montreal_time.strftime('%A, %B %d, %Y at %I:%M %p')}"

@function_tool()
async def get_clinic_info(context: RunContext_T) -> str:
    """Get dental clinic location and opening hours information."""
    return (
        "SmileRight Dental Clinic is located at 5561 St-Denis Street, Montreal, Canada. "
        "Our opening hours are Monday to Friday from 8:00 AM to 12:00 PM and 1:00 PM to 6:00 PM. "
        "We are closed on weekends."
    )

@function_tool()
async def to_greeter(context: RunContext_T) -> Agent:
    """Called when user asks any unrelated questions or requests
    any other services not in your job description."""
    curr_agent = context.session.current_agent
    if not isinstance(curr_agent, BaseAgent):
        raise TypeError("Current agent is not a BaseAgent")
    return (await curr_agent._transfer_to_agent("greeter", context))[0]

class BaseAgent(Agent):
    async def on_enter(self) -> None:
        agent_name = self.__class__.__name__
        logger.info(f"entering task {agent_name}")

        userdata: UserData = self.session.userdata
        chat_ctx = self.chat_ctx.copy()

        # Update in-memory metrics
        userdata.in_memory_metrics.update(f"agent_{agent_name}_entered", time.time())

        # Lightweight agent entry logging
        if userdata.enable_recording and userdata.db_manager and userdata.session_id:
            userdata.db_manager.queue_transcript(
                userdata.session_id,
                agent_name,
                "system",
                f"Agent {agent_name} entered"
            )

        # add the previous agent's chat history to the current agent
        if isinstance(userdata.prev_agent, Agent):
            truncated_chat_ctx = userdata.prev_agent.chat_ctx.copy(
                exclude_instructions=True, exclude_function_call=False
            ).truncate(max_items=6)
            existing_ids = {item.id for item in chat_ctx.items}
            items_copy = [item for item in truncated_chat_ctx.items if item.id not in existing_ids]
            chat_ctx.items.extend(items_copy)

        # Get current date/time for context
        current_time = datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')
        
        # add an instructions including the user data as assistant message
        chat_ctx.add_message(
            role="system",
            content=f"You are {agent_name} agent. Current date and time: {current_time}. "
                   f"SmileRight Dental Clinic is located at 5561 St-Denis Street, Montreal, Canada. "
                   f"Clinic hours: Monday to Friday 8:00 AM - 12:00 PM and 1:00 PM - 6:00 PM. "
                   f"Current user data is {userdata.summarize()}",
        )
        await self.update_chat_ctx(chat_ctx)
        self.session.generate_reply(tool_choice="none")

    async def _transfer_to_agent(self, name: str, context: RunContext_T) -> tuple[Agent, str]:
        userdata = context.userdata
        current_agent = context.session.current_agent
        next_agent = userdata.agents[name]
        userdata.prev_agent = current_agent
        
        # Update in-memory metrics
        userdata.in_memory_metrics.update("agent_transfers", 1)
        
        # Log the transfer asynchronously
        if userdata.enable_recording and userdata.db_manager and userdata.session_id:
            # Use asyncio.create_task to avoid blocking
            asyncio.create_task(userdata.db_manager.save_agent_transfer(
                userdata.session_id,
                current_agent.__class__.__name__,
                next_agent.__class__.__name__,
                f"Transfer from {current_agent.__class__.__name__} to {name}"
            ))

        return next_agent, f"Transferring to {name}."

class BookingAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            instructions=
            "You are a booking agent at SmileRight Dental Clinic located at 5561 St-Denis Street, Montreal, Canada. "
            "Our clinic hours are Monday to Friday from 8:00 AM to 12:00 PM and 1:00 PM to 6:00 PM. We are closed on weekends. "
            "Your jobs are to ask for the booking date and time (within our operating hours), then customer's name, "
            "phone number and the reason for the booking. Then confirm the reservation details with the customer. "
            "Always check that requested appointment times fall within our operating hours. "
            "Speak in clear, complete sentences with no special characters.",
            tools=[update_name, update_phone, update_booking_date_time, update_booking_reason, get_current_datetime, get_clinic_info],
            tts=openai.TTS(voice="ash"),
        )

    @function_tool()
    async def confirm_reservation(self, context: RunContext_T) -> str | tuple[Agent, str]:
        """Called when the user confirms the reservation."""
        userdata = context.userdata
        
        # Update in-memory metrics
        userdata.in_memory_metrics.update("reservation_attempt", 1)
        
        if not userdata.customer_name or not userdata.customer_phone:
            return "Please provide your name and phone number first."

        if not userdata.booking_date_time:
            return "Please provide reservation time first."

        # Update success metrics
        userdata.in_memory_metrics.update("reservation_confirmed", 1)
        
        # Log successful confirmation
        if userdata.enable_recording and userdata.db_manager and userdata.session_id:
            userdata.db_manager.queue_transcript(
                userdata.session_id,
                self.__class__.__name__,
                "system",
                "Reservation confirmed",
                metadata={"event": "reservation_confirmed"}
            )

        return await self._transfer_to_agent("greeter", context)

class Greeter(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are Denti Assist, the friendly automated scheduling assistant for SmileRight Dental Clinic. "
                "Our clinic is located at 5561 St-Denis Street, Montreal, Canada. "
                "We are open Monday to Friday from 8:00 AM to 12:00 PM and 1:00 PM to 6:00 PM. We are closed on weekends. "
                "Handle calls about appointments quickly and politely while sounding like a calm human receptionist. "
                "You can provide clinic information, current date/time, and help with appointment scheduling. "
                "Speak in clear, complete sentences with no special characters or symbols. "
                "Keep a warm, professional tone at a normal pace."
            ),
            llm=openai.LLM(parallel_tool_calls=False),
            tts=openai.TTS(voice="ash"),
            tools=[get_current_datetime, get_clinic_info],
        )

    @function_tool()
    async def to_booking_agent(self, context: RunContext_T) -> tuple[Agent, str]:
        """Called when user wants to make or update a booking."""
        return await self._transfer_to_agent("booking_agent", context)

# Optimized session class with minimal blocking operations
class OptimizedAgentSession(AgentSession[UserData]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_optimized_logging()
    
    def setup_optimized_logging(self):
        """Set up lightweight logging for chat messages"""
        original_generate_reply = self.generate_reply
        
        async def logged_generate_reply(*args, **kwargs):
            start_time = time.time()
            
            # Log the user message if available (before processing)
            if hasattr(self, 'chat_ctx') and self.chat_ctx.items and self.userdata.enable_recording and self.userdata.db_manager:
                last_item = self.chat_ctx.items[-1]
                if last_item.role == "user":
                    self.userdata.db_manager.queue_transcript(
                        self.userdata.session_id,
                        self.current_agent.__class__.__name__ if self.current_agent else "unknown",
                        "user",
                        last_item.content,
                        last_item.id
                    )
            
            # Call original method
            result = await original_generate_reply(*args, **kwargs)
            
            # Log response time
            response_time = time.time() - start_time
            self.userdata.in_memory_metrics.update("response_time", response_time)
            
            # Queue assistant response transcript asynchronously (non-blocking)
            if hasattr(self, 'chat_ctx') and self.chat_ctx.items and self.userdata.enable_recording and self.userdata.db_manager:
                last_item = self.chat_ctx.items[-1]
                if last_item.role == "assistant":
                    self.userdata.db_manager.queue_transcript(
                        self.userdata.session_id,
                        self.current_agent.__class__.__name__ if self.current_agent else "unknown",
                        "assistant",
                        last_item.content,
                        last_item.id
                    )
            
            return result
        
        self.generate_reply = logged_generate_reply

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

# Global variable to store recording preference
ENABLE_RECORDING = True

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Alex Dental Assistant Agent")
    parser.add_argument(
        "--no-recording", 
        action="store_true", 
        help="Disable recording of metrics and conversations to database"
    )
    parser.add_argument(
        "--disable-recording", 
        action="store_true", 
        help="Disable recording of metrics and conversations to database (alias for --no-recording)"
    )
    return parser.parse_args()

async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()
    
    # Get recording preference from global variable
    enable_recording = ENABLE_RECORDING
    
    # Initialize database manager and related components only if recording is enabled
    db_manager = None
    session_id = None
    metrics_collector = None
    
    if enable_recording:
        # Initialize optimized database with faster settings
        db_manager = AsyncDatabaseManager(
            batch_size=50,  # Smaller batches for faster processing
            flush_interval=2.0  # More frequent flushes
        )
        
        # Start background processing
        await db_manager.start_background_processing()
        
        # Create session in database
        session_id = await db_manager.create_session(
            room_id=ctx.room.name,
            participant_id=str(ctx.room.local_participant.sid) if ctx.room.local_participant else "unknown"
        )
        
        # Initialize metrics collector
        metrics_collector = OptimizedMetricsCollector(
            db_manager, 
            session_id,
            sample_rate=0.1,  # Sample 10% of metrics
            latency_threshold=0.1  # Only log high latencies
        )
        
        logger.info("Database recording enabled")
    else:
        logger.info("Database recording disabled")
    
    userdata = UserData(
        session_id=session_id,
        db_manager=db_manager,
        session_start_time=time.time(),
        metrics_collector=metrics_collector,
        enable_recording=enable_recording
    )
    
    userdata.agents.update({
        "greeter": Greeter(),
        "booking_agent": BookingAgent(),
    })
    
    # Use optimized session class
    session = OptimizedAgentSession(
        userdata=userdata,
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(voice="ash"),
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
        max_tool_steps=5,
    )
    
    # Enhanced usage collector with async metrics
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
        
        # Save metrics to database using optimized collector
        if userdata.enable_recording and userdata.metrics_collector:
            for metric in ev.metrics:
                # Use optimized collector with intelligent filtering
                if hasattr(metric, 'name') and hasattr(metric, 'value'):
                    userdata.metrics_collector.collect_metric(
                        metric.__class__.__name__,
                        metric.name,
                        float(metric.value),
                        getattr(metric, 'unit', None),
                        {"metric_data": str(metric)}
                    )

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")
        
        # End session in database
        if userdata.enable_recording and userdata.db_manager and userdata.session_id:
            duration = int(time.time() - userdata.session_start_time) if userdata.session_start_time else None
            await userdata.db_manager.end_session(userdata.session_id, duration)
            
            # Save final usage summary
            userdata.db_manager.queue_transcript(
                userdata.session_id,
                "system",
                "system",
                f"Session ended. Usage summary: {summary}",
                metadata={"event": "session_end", "usage_summary": str(summary)}
            )
            
            # Stop background processing and flush remaining data
            await userdata.db_manager.stop_background_processing()

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=userdata.agents["greeter"],
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

if __name__ == "__main__":
    # Parse command line arguments
    #args = parse_args()
    
    # Set global recording preference
    ENABLE_RECORDING = False #not (args.no_recording or args.disable_recording)
    
    #if not ENABLE_RECORDING:
    print("🔇 Recording disabled - metrics and conversations will not be saved to database")
    #else:
    #    print("📊 Recording enabled - metrics and conversations will be saved to database")
    
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
