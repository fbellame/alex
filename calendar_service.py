"""
Calendar Service for SmileRight Dental Clinic
Provides calendar integration for appointment scheduling
"""

import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import json

logger = logging.getLogger("dental_assistant.calendar")

@dataclass
class TimeSlot:
    date: str  # YYYY-MM-DD format
    time: str  # HH:MM format
    duration_minutes: int
    available: bool = True

@dataclass
class Appointment:
    appointment_id: str
    patient_id: str
    date: str
    time: str
    duration_minutes: int
    treatment_type: str
    status: str = "scheduled"

class CalendarService:
    """
    Calendar service for managing clinic appointments
    This is a simplified implementation - in production you'd integrate with
    Google Calendar, Outlook, or a dedicated scheduling system
    """
    
    def __init__(self):
        self.clinic_hours = {
            'monday': [('08:00', '12:00'), ('13:00', '18:00')],
            'tuesday': [('08:00', '12:00'), ('13:00', '18:00')],
            'wednesday': [('08:00', '12:00'), ('13:00', '18:00')],
            'thursday': [('08:00', '12:00'), ('13:00', '18:00')],
            'friday': [('08:00', '12:00'), ('13:00', '18:00')],
            'saturday': [],  # Closed
            'sunday': []     # Closed
        }
        
        # In-memory storage for demo - in production use database
        self.appointments: Dict[str, Appointment] = {}
        self.blocked_times: List[TimeSlot] = []
        
    def _get_weekday_name(self, date_str: str) -> str:
        """Get weekday name from date string"""
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        return date_obj.strftime('%A').lower()
    
    def _time_to_minutes(self, time_str: str) -> int:
        """Convert HH:MM to minutes since midnight"""
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes
    
    def _minutes_to_time(self, minutes: int) -> str:
        """Convert minutes since midnight to HH:MM"""
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours:02d}:{mins:02d}"
    
    def is_clinic_open(self, date_str: str, time_str: str) -> bool:
        """Check if clinic is open at given date and time"""
        weekday = self._get_weekday_name(date_str)
        
        if weekday not in self.clinic_hours or not self.clinic_hours[weekday]:
            return False
        
        time_minutes = self._time_to_minutes(time_str)
        
        for start_time, end_time in self.clinic_hours[weekday]:
            start_minutes = self._time_to_minutes(start_time)
            end_minutes = self._time_to_minutes(end_time)
            
            if start_minutes <= time_minutes < end_minutes:
                return True
        
        return False
    
    def get_available_slots(self, date_str: str, duration_minutes: int = 30) -> List[TimeSlot]:
        """Get available time slots for a given date"""
        weekday = self._get_weekday_name(date_str)
        
        if weekday not in self.clinic_hours or not self.clinic_hours[weekday]:
            return []
        
        available_slots = []
        
        for start_time, end_time in self.clinic_hours[weekday]:
            start_minutes = self._time_to_minutes(start_time)
            end_minutes = self._time_to_minutes(end_time)
            
            # Generate 30-minute slots
            current_time = start_minutes
            while current_time + duration_minutes <= end_minutes:
                time_str = self._minutes_to_time(current_time)
                
                # Check if slot is available (not booked)
                if self._is_slot_available(date_str, time_str, duration_minutes):
                    available_slots.append(TimeSlot(
                        date=date_str,
                        time=time_str,
                        duration_minutes=duration_minutes,
                        available=True
                    ))
                
                current_time += 30  # 30-minute intervals
        
        return available_slots
    
    def _is_slot_available(self, date_str: str, time_str: str, duration_minutes: int) -> bool:
        """Check if a specific time slot is available"""
        slot_start = self._time_to_minutes(time_str)
        slot_end = slot_start + duration_minutes
        
        # Check against existing appointments
        for appointment in self.appointments.values():
            if appointment.date == date_str and appointment.status in ['scheduled', 'confirmed']:
                apt_start = self._time_to_minutes(appointment.time)
                apt_end = apt_start + appointment.duration_minutes
                
                # Check for overlap
                if not (slot_end <= apt_start or slot_start >= apt_end):
                    return False
        
        # Check against blocked times
        for blocked in self.blocked_times:
            if blocked.date == date_str:
                blocked_start = self._time_to_minutes(blocked.time)
                blocked_end = blocked_start + blocked.duration_minutes
                
                if not (slot_end <= blocked_start or slot_start >= blocked_end):
                    return False
        
        return True
    
    async def book_appointment(self, appointment: Appointment) -> bool:
        """Book an appointment if the slot is available"""
        try:
            # Validate clinic hours
            if not self.is_clinic_open(appointment.date, appointment.time):
                logger.warning(f"Attempted to book outside clinic hours: {appointment.date} {appointment.time}")
                return False
            
            # Check availability
            if not self._is_slot_available(appointment.date, appointment.time, appointment.duration_minutes):
                logger.warning(f"Time slot not available: {appointment.date} {appointment.time}")
                return False
            
            # Book the appointment
            self.appointments[appointment.appointment_id] = appointment
            logger.info(f"Appointment booked: {appointment.appointment_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error booking appointment: {e}")
            return False
    
    async def cancel_appointment(self, appointment_id: str) -> bool:
        """Cancel an appointment"""
        try:
            if appointment_id in self.appointments:
                self.appointments[appointment_id].status = "cancelled"
                logger.info(f"Appointment cancelled: {appointment_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error cancelling appointment: {e}")
            return False
    
    def get_appointments_for_date(self, date_str: str) -> List[Appointment]:
        """Get all appointments for a specific date"""
        return [apt for apt in self.appointments.values() 
                if apt.date == date_str and apt.status in ['scheduled', 'confirmed']]
    
    def suggest_alternative_times(self, preferred_date: str, duration_minutes: int = 30, 
                                days_ahead: int = 7) -> List[TimeSlot]:
        """Suggest alternative appointment times if preferred slot is not available"""
        suggestions = []
        
        # Try the preferred date first
        slots = self.get_available_slots(preferred_date, duration_minutes)
        if slots:
            return slots[:3]  # Return first 3 available slots
        
        # Try subsequent days
        base_date = datetime.strptime(preferred_date, '%Y-%m-%d')
        for i in range(1, days_ahead + 1):
            check_date = base_date + timedelta(days=i)
            date_str = check_date.strftime('%Y-%m-%d')
            
            slots = self.get_available_slots(date_str, duration_minutes)
            if slots:
                suggestions.extend(slots[:2])  # Add first 2 slots from each day
                
                if len(suggestions) >= 5:  # Limit to 5 suggestions
                    break
        
        return suggestions[:5]
    
    def block_time(self, date_str: str, time_str: str, duration_minutes: int, reason: str = "Blocked"):
        """Block a time slot (for lunch, meetings, etc.)"""
        blocked_slot = TimeSlot(
            date=date_str,
            time=time_str,
            duration_minutes=duration_minutes,
            available=False
        )
        self.blocked_times.append(blocked_slot)
        logger.info(f"Time blocked: {date_str} {time_str} for {duration_minutes} minutes - {reason}")
    
    def get_clinic_schedule_summary(self, date_str: str) -> Dict:
        """Get a summary of the clinic schedule for a date"""
        appointments = self.get_appointments_for_date(date_str)
        available_slots = self.get_available_slots(date_str)
        
        return {
            'date': date_str,
            'weekday': self._get_weekday_name(date_str).title(),
            'is_open': bool(self.clinic_hours.get(self._get_weekday_name(date_str))),
            'total_appointments': len(appointments),
            'available_slots': len(available_slots),
            'appointments': [
                {
                    'time': apt.time,
                    'duration': apt.duration_minutes,
                    'treatment': apt.treatment_type,
                    'status': apt.status
                } for apt in sorted(appointments, key=lambda x: x.time)
            ],
            'next_available': available_slots[0].time if available_slots else None
        }

# Global calendar service instance
calendar_service = CalendarService()

# Initialize some blocked times (lunch breaks, etc.)
def initialize_calendar():
    """Initialize calendar with standard blocked times"""
    # Block lunch time every weekday
    from datetime import date, timedelta
    
    today = date.today()
    for i in range(30):  # Block for next 30 days
        check_date = today + timedelta(days=i)
        weekday = check_date.strftime('%A').lower()
        
        if weekday in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']:
            calendar_service.block_time(
                check_date.strftime('%Y-%m-%d'),
                '12:00',
                60,  # 1 hour lunch
                'Lunch break'
            )

# Initialize when module is imported
initialize_calendar()
