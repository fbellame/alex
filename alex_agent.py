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
from calendar_service import calendar_service, Appointment as CalendarAppointment

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
    
    # Patient management fields
    patient_id: Optional[str] = None
    is_returning_patient: Optional[bool] = None
    patient_verified: bool = False
    date_of_birth: Optional[str] = None
    email: Optional[str] = None
    
    # Intent tracking
    user_intent: Optional[str] = None  # 'information', 'booking', 'general'
    requested_treatment: Optional[str] = None

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
async def update_date_of_birth(
    date_of_birth: Annotated[str, Field(description="The customer's date of birth in YYYY-MM-DD format")],
    context: RunContext_T,
) -> str:
    """Called when the user provides their date of birth for patient verification."""
    userdata = context.userdata
    userdata.date_of_birth = date_of_birth
    userdata.save_to_db()
    
    # Update in-memory metrics
    userdata.in_memory_metrics.update("date_of_birth_updated", 1)
    
    return f"Date of birth updated to {date_of_birth}"

@function_tool()
async def update_email(
    email: Annotated[str, Field(description="The customer's email address")],
    context: RunContext_T,
) -> str:
    """Called when the user provides their email address."""
    userdata = context.userdata
    userdata.email = email
    userdata.save_to_db()
    
    # Update in-memory metrics
    userdata.in_memory_metrics.update("email_updated", 1)
    
    return f"Email updated to {email}"

@function_tool()
async def search_patient_by_phone_and_dob(
    phone: Annotated[str, Field(description="Patient's phone number in format 1-XXX-XXX-XXXX")],
    date_of_birth: Annotated[str, Field(description="Patient's date of birth in YYYY-MM-DD format")],
    context: RunContext_T,
) -> str:
    """Search for existing patient by phone number and date of birth."""
    userdata = context.userdata
    
    if not userdata.db_manager:
        return "Patient lookup is not available at this time."
    
    try:
        patient = await userdata.db_manager.search_patient_by_phone_and_dob(phone, date_of_birth)
        
        if patient:
            # Update userdata with patient information
            userdata.patient_id = patient['patient_id']
            userdata.customer_name = patient['name']
            userdata.customer_phone = patient['phone']
            userdata.date_of_birth = patient['date_of_birth']
            userdata.email = patient.get('email')
            userdata.is_returning_patient = True
            userdata.patient_verified = True
            
            userdata.save_to_db()
            userdata.in_memory_metrics.update("patient_found", 1)
            
            return f"Welcome back, {patient['name']}! I found your record in our system. How can I help you today?"
        else:
            userdata.in_memory_metrics.update("patient_not_found", 1)
            return "I couldn't find a patient record with that phone number and date of birth. Would you like me to register you as a new patient?"
            
    except Exception as e:
        logger.error(f"Error searching for patient: {e}")
        return "I'm having trouble accessing patient records right now. Let me help you as a new patient."

@function_tool()
async def create_patient_record(
    name: Annotated[str, Field(description="Patient's full name")],
    phone: Annotated[str, Field(description="Patient's phone number in format 1-XXX-XXX-XXXX")],
    date_of_birth: Annotated[str, Field(description="Patient's date of birth in YYYY-MM-DD format")],
    context: RunContext_T,
    email: Annotated[Optional[str], Field(description="Patient's email address (optional)")] = None,
) -> str:
    """Create a new patient record in the system."""
    userdata = context.userdata
    
    if not userdata.db_manager:
        return "Patient registration is not available at this time."
    
    try:
        patient_id = await userdata.db_manager.create_patient_record(
            name=name,
            phone=phone,
            date_of_birth=date_of_birth,
            email=email
        )
        
        # Update userdata
        userdata.patient_id = patient_id
        userdata.customer_name = name
        userdata.customer_phone = phone
        userdata.date_of_birth = date_of_birth
        userdata.email = email
        userdata.is_returning_patient = False
        userdata.patient_verified = True
        
        userdata.save_to_db()
        userdata.in_memory_metrics.update("new_patient_registered", 1)
        
        return f"Great! I've registered you as a new patient, {name}. Your patient record has been created. How can I help you today?"
        
    except Exception as e:
        logger.error(f"Error creating patient record: {e}")
        return "I'm having trouble creating your patient record right now. Let me still help you with your inquiry."

@function_tool()
async def get_treatment_info(
    context: RunContext_T,
    treatment_name: Annotated[Optional[str], Field(description="Name of the treatment to get information about")] = None,
    category: Annotated[Optional[str], Field(description="Category of treatments (preventive, diagnostic, restorative, etc.)")] = None,
) -> str:
    """Get information about dental treatments and their pricing."""
    userdata = context.userdata
    
    if not userdata.db_manager:
        return "Treatment information is not available at this time."
    
    try:
        treatments = await userdata.db_manager.get_treatment_info(treatment_name, category)
        
        if not treatments:
            return "I couldn't find information about that treatment. Let me know what specific treatment you're interested in."
        
        # Format treatment information
        info_parts = []
        for treatment in treatments[:5]:  # Limit to 5 treatments to avoid overwhelming
            price_range = f"${treatment['price_range_min']}-${treatment['price_range_max']}"
            duration = f"{treatment['duration_minutes']} minutes"
            
            info_parts.append(
                f"{treatment['name']}: {treatment['description']}. "
                f"Price range: {price_range}. Duration: {duration}."
            )
        
        result = "Here's information about our treatments:\n\n" + "\n\n".join(info_parts)
        
        if len(treatments) > 5:
            result += f"\n\nI found {len(treatments)} treatments total. Would you like information about any specific treatment?"
        
        userdata.in_memory_metrics.update("treatment_info_requested", 1)
        return result
        
    except Exception as e:
        logger.error(f"Error getting treatment info: {e}")
        return "I'm having trouble accessing treatment information right now. Please call our office for specific pricing details."

@function_tool()
async def search_treatments_by_keyword(
    keyword: Annotated[str, Field(description="Keyword to search for in treatment names or descriptions")],
    context: RunContext_T,
) -> str:
    """Search for treatments by keyword."""
    userdata = context.userdata
    
    if not userdata.db_manager:
        return "Treatment search is not available at this time."
    
    try:
        treatments = await userdata.db_manager.search_treatments_by_keyword(keyword)
        
        if not treatments:
            return f"I couldn't find any treatments related to '{keyword}'. Could you try a different term or ask about a specific treatment?"
        
        # Format search results
        info_parts = []
        for treatment in treatments[:3]:  # Limit to 3 for voice response
            price_range = f"${treatment['price_range_min']}-${treatment['price_range_max']}"
            info_parts.append(f"{treatment['name']}: {price_range}")
        
        result = f"I found {len(treatments)} treatments related to '{keyword}':\n\n" + "\n".join(info_parts)
        
        if len(treatments) > 3:
            result += "\n\nWould you like more details about any of these treatments?"
        
        userdata.in_memory_metrics.update("treatment_search_performed", 1)
        return result
        
    except Exception as e:
        logger.error(f"Error searching treatments: {e}")
        return "I'm having trouble searching for treatments right now. Please let me know what specific treatment you're interested in."

@function_tool()
async def get_treatment_price_and_duration(
    treatment_name: Annotated[str, Field(description="Name of the treatment to get price and duration for")],
    context: RunContext_T,
) -> str:
    """Get specific price and duration information for a dental treatment.
    This function provides concise, voice-friendly responses about treatment costs and time requirements."""
    userdata = context.userdata
    
    if not userdata.db_manager:
        return "Treatment pricing information is not available at this time."
    
    try:
        treatment = await userdata.db_manager.get_treatment_price_duration(treatment_name)
        
        if not treatment:
            return f"I couldn't find pricing information for '{treatment_name}'. Could you try a different treatment name or ask me to search for treatments?"
        
        # Store the requested treatment for booking context
        userdata.requested_treatment = treatment['name']
        userdata.save_to_db()
        
        # Format price range in a voice-friendly way
        min_price = treatment['price_range_min']
        max_price = treatment['price_range_max']
        duration = treatment['duration_minutes']
        
        # Convert duration to user-friendly format
        if duration >= 60:
            hours = duration // 60
            minutes = duration % 60
            if minutes == 0:
                duration_text = f"{hours} hour{'s' if hours > 1 else ''}"
            else:
                duration_text = f"{hours} hour{'s' if hours > 1 else ''} and {minutes} minutes"
        else:
            duration_text = f"{duration} minutes"
        
        # Create natural speech response
        if min_price == max_price:
            price_text = f"{min_price} dollars"
        else:
            price_text = f"between {min_price} and {max_price} dollars"
        
        result = (f"For {treatment['name']}, the cost is {price_text} "
                 f"and the appointment typically takes {duration_text}.")
        
        # Add brief description if available
        if treatment.get('description'):
            result += f" This treatment involves {treatment['description'].lower()}."
        
        # Track metrics
        userdata.in_memory_metrics.update("treatment_price_duration_requested", 1)
        
        # Log the query
        if userdata.enable_recording and userdata.db_manager and userdata.session_id:
            userdata.db_manager.queue_transcript(
                userdata.session_id,
                context.session.current_agent.__class__.__name__,
                "function_call",
                f"Price/duration query for: {treatment_name}",
                metadata={"function": "get_treatment_price_and_duration", "treatment": treatment['name']}
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting treatment price and duration: {e}")
        return "I'm having trouble accessing treatment pricing right now. Please call our office at your convenience for specific pricing details."

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
        
        # For Greeter agent, initiate conversation immediately
        if agent_name == "Greeter":
            chat_ctx.add_message(
                role="user",
                content="[System: User has connected to the call]"
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

        # Silent transfer - no message to user
        return next_agent, ""

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

class PatientIdentificationAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are the patient identification agent for SmileRight Dental Clinic. "
                "Your job is to determine if the caller is a new patient or a returning patient. "
                "Ask: 'Are you a new patient or have you visited our clinic before?' "
                "Based on their response, transfer them to the appropriate agent. "
                "Be friendly and professional. Speak in clear, complete sentences."
            ),
            llm=openai.LLM(parallel_tool_calls=False),
            tts=openai.TTS(voice="ash"),
            tools=[get_current_datetime, get_clinic_info],
        )

    @function_tool()
    async def to_patient_lookup(self, context: RunContext_T) -> tuple[Agent, str]:
        """Called when user indicates they are a returning patient."""
        userdata = context.userdata
        userdata.is_returning_patient = True
        return await self._transfer_to_agent("patient_lookup", context)

    @function_tool()
    async def to_registration_agent(self, context: RunContext_T) -> tuple[Agent, str]:
        """Called when user indicates they are a new patient."""
        userdata = context.userdata
        userdata.is_returning_patient = False
        return await self._transfer_to_agent("registration_agent", context)

class PatientLookupAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are the patient lookup agent for SmileRight Dental Clinic. "
                "Your job is to verify returning patients by asking for their phone number and date of birth. "
                "Ask for phone number in format 1-XXX-XXX-XXXX and date of birth in YYYY-MM-DD format. "
                "Once you have both pieces of information, search for the patient record. "
                "If found, welcome them back and ask how you can help. "
                "If not found, offer to register them as a new patient. "
                "Be friendly and professional."
            ),
            llm=openai.LLM(parallel_tool_calls=False),
            tts=openai.TTS(voice="ash"),
            tools=[update_phone, update_date_of_birth, search_patient_by_phone_and_dob, get_current_datetime],
        )

    @function_tool()
    async def to_booking_agent(self, context: RunContext_T) -> tuple[Agent, str]:
        """Called when verified patient wants to make a booking."""
        return await self._transfer_to_agent("enhanced_booking_agent", context)

    @function_tool()
    async def to_info_agent(self, context: RunContext_T) -> tuple[Agent, str]:
        """Called when verified patient wants treatment information."""
        userdata = context.userdata
        userdata.user_intent = "information"
        return await self._transfer_to_agent("info_agent", context)

    @function_tool()
    async def to_registration_agent(self, context: RunContext_T) -> tuple[Agent, str]:
        """Called when patient is not found and wants to register as new patient."""
        userdata = context.userdata
        userdata.is_returning_patient = False
        return await self._transfer_to_agent("registration_agent", context)

class RegistrationAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are the patient registration agent for SmileRight Dental Clinic. "
                "Your job is to register new patients by collecting their information: "
                "name, phone number (1-XXX-XXX-XXXX format), date of birth (YYYY-MM-DD format), and optionally email. "
                "After collecting the information, create their patient record. "
                "Then ask what they need help with: booking an appointment or information about treatments. "
                "Be friendly, professional, and thorough in collecting information."
            ),
            llm=openai.LLM(parallel_tool_calls=False),
            tts=openai.TTS(voice="ash"),
            tools=[update_name, update_phone, update_date_of_birth, update_email, create_patient_record, get_current_datetime],
        )

    @function_tool()
    async def to_booking_agent(self, context: RunContext_T) -> tuple[Agent, str]:
        """Called when new patient wants to make a booking."""
        userdata = context.userdata
        userdata.user_intent = "booking"
        return await self._transfer_to_agent("enhanced_booking_agent", context)

    @function_tool()
    async def to_info_agent(self, context: RunContext_T) -> tuple[Agent, str]:
        """Called when new patient wants treatment information."""
        userdata = context.userdata
        userdata.user_intent = "information"
        return await self._transfer_to_agent("info_agent", context)

class InfoAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are the information agent for SmileRight Dental Clinic. "
                "Your job is to provide information about dental treatments, pricing, and procedures. "
                "You have access to our complete treatment database with pricing ranges and duration information. "
                "When customers ask specifically about treatment prices or how long treatments take, use the get_treatment_price_and_duration function for the most accurate and voice-friendly response. "
                "For general treatment information or searches, use the other available tools. "
                "Answer questions about treatments, costs, duration, and what to expect. "
                "If a patient decides they want to book an appointment after getting information, transfer them to booking. "
                "Be knowledgeable, helpful, and professional. Speak in clear, complete sentences."
            ),
            llm=openai.LLM(parallel_tool_calls=False),
            tts=openai.TTS(voice="ash"),
            tools=[get_treatment_info, search_treatments_by_keyword, get_treatment_price_and_duration, get_current_datetime, get_clinic_info],
        )

    @function_tool()
    async def to_booking_agent(self, context: RunContext_T) -> tuple[Agent, str]:
        """Called when patient wants to book an appointment after getting information."""
        userdata = context.userdata
        userdata.user_intent = "booking"
        return await self._transfer_to_agent("enhanced_booking_agent", context)

class EnhancedBookingAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are the enhanced booking agent at SmileRight Dental Clinic. "
                "You work with both new and returning patients who already have patient records. "
                "Your job is to schedule appointments by collecting: date, time, and treatment type. "
                "Our clinic hours are Monday to Friday 8:00 AM - 12:00 PM and 1:00 PM - 6:00 PM. "
                "Always verify appointment times are within business hours. "
                "If the patient asks about treatment pricing or duration during booking, use get_treatment_price_and_duration for accurate information. "
                "If the patient doesn't have complete information (name, phone), collect it. "
                "Create the appointment in our system and confirm all details. "
                "Be professional and thorough."
            ),
            llm=openai.LLM(parallel_tool_calls=False),
            tts=openai.TTS(voice="ash"),
            tools=[update_name, update_phone, update_booking_date_time, update_booking_reason, 
                   get_current_datetime, get_clinic_info, get_treatment_info, get_treatment_price_and_duration],
        )

    @function_tool()
    async def confirm_appointment(self, context: RunContext_T) -> str:
        """Called when the patient confirms their appointment details."""
        userdata = context.userdata
        
        # Verify we have all required information
        if not userdata.patient_verified:
            return "I need to verify your patient information first. Please provide your name and phone number."
        
        if not userdata.booking_date_time:
            return "Please provide your preferred appointment date and time."
        
        if not userdata.booking_reason:
            return "Please let me know what type of treatment or service you need."
        
        # Create appointment in database if we have a patient ID
        if userdata.db_manager and userdata.patient_id:
            try:
                # Parse date and time (this is simplified - in production you'd want better parsing)
                appointment_id = await userdata.db_manager.create_appointment(
                    patient_id=userdata.patient_id,
                    appointment_date=userdata.booking_date_time.split()[0],  # Simplified parsing
                    appointment_time="09:00",  # Simplified - would parse actual time
                    treatment_type=userdata.booking_reason,
                    notes=f"Appointment scheduled via voice assistant"
                )
                
                userdata.in_memory_metrics.update("appointment_created", 1)
                
                return (f"Perfect! I've confirmed your appointment for {userdata.booking_date_time} "
                       f"for {userdata.booking_reason}. Your appointment ID is {appointment_id[:8]}. "
                       f"We'll see you at SmileRight Dental Clinic. Is there anything else I can help you with?")
                       
            except Exception as e:
                logger.error(f"Error creating appointment: {e}")
                return (f"I've noted your appointment request for {userdata.booking_date_time} "
                       f"for {userdata.booking_reason}. Our staff will call you to confirm the details. "
                       f"Is there anything else I can help you with?")
        else:
            return (f"I've noted your appointment request for {userdata.booking_date_time} "
                   f"for {userdata.booking_reason}. Our staff will call you to confirm the details. "
                   f"Is there anything else I can help you with?")

class Greeter(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are Denti Assist, the friendly automated scheduling assistant for SmileRight Dental Clinic. "
                "Our clinic is located at 5561 St-Denis Street, Montreal, Canada. "
                "We are open Monday to Friday from 8:00 AM to 12:00 PM and 1:00 PM to 6:00 PM. We are closed on weekends. "
                "IMMEDIATELY when someone connects, greet them warmly and ask how you can help them today. "
                "If they ask about treatment information, pricing, or procedures, provide the information directly using available tools. "
                "You do NOT need patient registration or identification to provide basic treatment information and pricing. "
                "Only transfer to patient identification if they specifically want to book an appointment. "
                "For general treatment information and pricing, help them directly without any transfers. "
                "Speak in clear, complete sentences with no special characters or symbols. "
                "Keep a warm, professional tone at a normal pace. "
                "Start every conversation with a greeting like: 'Hello! Thank you for calling SmileRight Dental Clinic. This is Denti Assist, your automated scheduling assistant. How can I help you today?'"
            ),
            llm=openai.LLM(parallel_tool_calls=False),
            tts=openai.TTS(voice="ash"),
            tools=[get_current_datetime, get_clinic_info, get_treatment_info, search_treatments_by_keyword, get_treatment_price_and_duration],
        )

    @function_tool()
    async def to_patient_identification(self, context: RunContext_T) -> tuple[Agent, str]:
        """Called only when user specifically wants to book an appointment."""
        return await self._transfer_to_agent("patient_identification", context)

    @function_tool()
    async def to_booking_agent(self, context: RunContext_T) -> tuple[Agent, str]:
        """Called when user wants to make or update a booking."""
        return await self._transfer_to_agent("patient_identification", context)

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
        "patient_identification": PatientIdentificationAgent(),
        "patient_lookup": PatientLookupAgent(),
        "registration_agent": RegistrationAgent(),
        "info_agent": InfoAgent(),
        "enhanced_booking_agent": EnhancedBookingAgent(),
        "booking_agent": BookingAgent(),  # Keep for legacy compatibility
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
