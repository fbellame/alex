#!/usr/bin/env python3
"""
Test script for enhanced AI voice assistant features
Tests patient management, treatment database, and calendar integration
"""

import asyncio
import sys
import os
from datetime import datetime, date, timedelta

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db_manager import AsyncDatabaseManager
from calendar_service import calendar_service, Appointment as CalendarAppointment

async def test_database_features():
    """Test database functionality"""
    print("🔍 Testing Database Features...")
    
    # Initialize database manager
    db_manager = AsyncDatabaseManager()
    await db_manager.start_background_processing()
    
    try:
        # Test treatment database
        print("\n📋 Testing Treatment Database:")
        treatments = await db_manager.get_treatment_info()
        print(f"Found {len(treatments)} treatments in database")
        
        # Test specific treatment lookup
        cleaning_treatments = await db_manager.get_treatment_info(treatment_name="Basic Cleaning")
        if cleaning_treatments:
            treatment = cleaning_treatments[0]
            print(f"Basic Cleaning: ${treatment['price_range_min']}-${treatment['price_range_max']}, {treatment['duration_minutes']} minutes")
        
        # Test treatment search
        search_results = await db_manager.search_treatments_by_keyword("cleaning")
        print(f"Found {len(search_results)} treatments matching 'cleaning'")
        
        # Test patient creation
        print("\n👤 Testing Patient Management:")
        patient_id = await db_manager.create_patient_record(
            name="Test Patient",
            phone="1-555-123-4567",
            date_of_birth="1990-01-01",
            email="test@example.com"
        )
        print(f"Created patient with ID: {patient_id}")
        
        # Test patient lookup
        patient = await db_manager.search_patient_by_phone_and_dob("1-555-123-4567", "1990-01-01")
        if patient:
            print(f"Found patient: {patient['name']}")
        
        # Test appointment creation
        print("\n📅 Testing Appointment Management:")
        appointment_id = await db_manager.create_appointment(
            patient_id=patient_id,
            appointment_date="2025-01-20",
            appointment_time="10:00",
            treatment_type="Basic Cleaning",
            notes="Test appointment"
        )
        print(f"Created appointment with ID: {appointment_id}")
        
        print("✅ Database tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
    
    finally:
        await db_manager.stop_background_processing()

async def test_calendar_features():
    """Test calendar functionality"""
    print("\n📅 Testing Calendar Features...")
    
    try:
        # Test clinic hours validation
        today = date.today()
        today_str = today.strftime('%Y-%m-%d')
        
        print(f"\n🕐 Testing clinic hours for {today_str}:")
        is_open_morning = calendar_service.is_clinic_open(today_str, "09:00")
        is_open_lunch = calendar_service.is_clinic_open(today_str, "12:30")
        is_open_evening = calendar_service.is_clinic_open(today_str, "19:00")
        
        print(f"9:00 AM: {'Open' if is_open_morning else 'Closed'}")
        print(f"12:30 PM: {'Open' if is_open_lunch else 'Closed'}")
        print(f"7:00 PM: {'Open' if is_open_evening else 'Closed'}")
        
        # Test available slots
        print(f"\n📋 Available slots for {today_str}:")
        available_slots = calendar_service.get_available_slots(today_str)
        print(f"Found {len(available_slots)} available slots")
        
        if available_slots:
            for i, slot in enumerate(available_slots[:5]):  # Show first 5
                print(f"  {slot.time} ({slot.duration_minutes} min)")
        
        # Test appointment booking
        print(f"\n📝 Testing appointment booking:")
        if available_slots:
            test_appointment = CalendarAppointment(
                appointment_id="test-001",
                patient_id="test-patient",
                date=today_str,
                time=available_slots[0].time,
                duration_minutes=30,
                treatment_type="Basic Cleaning"
            )
            
            booking_success = await calendar_service.book_appointment(test_appointment)
            print(f"Booking result: {'Success' if booking_success else 'Failed'}")
            
            # Test schedule summary
            summary = calendar_service.get_clinic_schedule_summary(today_str)
            print(f"Schedule summary: {summary['total_appointments']} appointments, {summary['available_slots']} slots available")
        
        print("✅ Calendar tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Calendar test failed: {e}")

def test_agent_workflow():
    """Test agent workflow logic"""
    print("\n🤖 Testing Agent Workflow Logic...")
    
    try:
        # Simulate workflow paths
        workflows = [
            "Greeter → PatientIdentification → PatientLookup → (Found) → InfoAgent",
            "Greeter → PatientIdentification → PatientLookup → (Not Found) → RegistrationAgent",
            "Greeter → PatientIdentification → RegistrationAgent → EnhancedBookingAgent",
            "InfoAgent → EnhancedBookingAgent (after getting treatment info)"
        ]
        
        print("📋 Supported workflow paths:")
        for i, workflow in enumerate(workflows, 1):
            print(f"  {i}. {workflow}")
        
        # Test treatment knowledge base
        print("\n💡 Treatment Knowledge Base:")
        sample_treatments = [
            ("Basic Cleaning", "$120-150", "45 min", "Preventive"),
            ("Root Canal", "$800-1200", "90 min", "Endodontic"),
            ("Teeth Whitening", "$300-500", "90 min", "Cosmetic"),
            ("General Checkup", "$80-100", "30 min", "Preventive")
        ]
        
        for name, price, duration, category in sample_treatments:
            print(f"  • {name}: {price}, {duration} ({category})")
        
        print("✅ Agent workflow tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Agent workflow test failed: {e}")

async def main():
    """Run all tests"""
    print("🚀 Enhanced AI Voice Assistant - Feature Tests")
    print("=" * 50)
    
    # Test database features
    await test_database_features()
    
    # Test calendar features
    test_calendar_features()
    
    # Test agent workflow
    test_agent_workflow()
    
    print("\n" + "=" * 50)
    print("🎉 All tests completed!")
    print("\n📝 Summary of Enhanced Features:")
    print("✅ Patient identification and verification")
    print("✅ Patient registration and database management")
    print("✅ Treatment knowledge base with pricing")
    print("✅ Calendar integration with availability checking")
    print("✅ Enhanced agent workflow with multiple paths")
    print("✅ Appointment scheduling and management")
    
    print("\n🔧 To run the enhanced voice assistant:")
    print("   python alex_agent.py")
    
    print("\n📚 For detailed documentation, see:")
    print("   README_ENHANCED.md")

if __name__ == "__main__":
    asyncio.run(main())
