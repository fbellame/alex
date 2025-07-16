import pandas as pd
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import matplotlib.pyplot as plt
import seaborn as sns
from db_manager import AsyncDatabaseManager

class AsyncDataAnalyzer:
    def __init__(self, db_path: str = "dental_assistant.db"):
        self.db_manager = AsyncDatabaseManager(db_path)
    
    async def get_sessions_dataframe(self) -> pd.DataFrame:
        """Get all sessions as a pandas DataFrame"""
        async with self.db_manager.get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM sessions ORDER BY start_time")
            sessions = await cursor.fetchall()
            
        df = pd.DataFrame([dict(session) for session in sessions])
        if not df.empty:
            df['start_time'] = pd.to_datetime(df['start_time'])
            df['end_time'] = pd.to_datetime(df['end_time'])
        return df
    
    async def get_transcripts_dataframe(self, session_id: str = None) -> pd.DataFrame:
        """Get transcripts as a pandas DataFrame"""
        async with self.db_manager.get_connection() as conn:
            if session_id:
                cursor = await conn.execute(
                    "SELECT * FROM transcripts WHERE session_id = ? ORDER BY timestamp",
                    (session_id,)
                )
            else:
                cursor = await conn.execute("SELECT * FROM transcripts ORDER BY timestamp")
            
            transcripts = await cursor.fetchall()
        
        df = pd.DataFrame([dict(transcript) for transcript in transcripts])
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            # Parse metadata JSON
            df['metadata_parsed'] = df['metadata'].apply(
                lambda x: json.loads(x) if x else {}
            )
        return df
    
    async def get_metrics_dataframe(self, session_id: str = None) -> pd.DataFrame:
        """Get metrics as a pandas DataFrame"""
        async with self.db_manager.get_connection() as conn:
            if session_id:
                cursor = await conn.execute(
                    "SELECT * FROM metrics WHERE session_id = ? ORDER BY timestamp",
                    (session_id,)
                )
            else:
                cursor = await conn.execute("SELECT * FROM metrics ORDER BY timestamp")
            
            metrics = await cursor.fetchall()
        
        df = pd.DataFrame([dict(metric) for metric in metrics])
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            # Parse metadata JSON
            df['metadata_parsed'] = df['metadata'].apply(
                lambda x: json.loads(x) if x else {}
            )
        return df
    
    async def get_user_data_dataframe(self, session_id: str = None) -> pd.DataFrame:
        """Get user data as a pandas DataFrame"""
        async with self.db_manager.get_connection() as conn:
            if session_id:
                cursor = await conn.execute(
                    "SELECT * FROM user_data WHERE session_id = ? ORDER BY updated_at",
                    (session_id,)
                )
            else:
                cursor = await conn.execute("SELECT * FROM user_data ORDER BY updated_at")
            
            user_data = await cursor.fetchall()
        
        df = pd.DataFrame([dict(data) for data in user_data])
        if not df.empty:
            df['updated_at'] = pd.to_datetime(df['updated_at'])
            # Parse data snapshot JSON
            df['data_snapshot_parsed'] = df['data_snapshot'].apply(
                lambda x: json.loads(x) if x else {}
            )
        return df
    
    async def generate_session_report(self, session_id: str) -> Dict[str, Any]:
        """Generate a comprehensive report for a specific session"""
        session_data = await self.db_manager.get_session_data(session_id)
        if not session_data:
            return {"error": "Session not found"}
        
        # Basic session info
        session_info = session_data['session']
        user_data = session_data['user_data']
        transcripts = session_data['transcripts']
        metrics = session_data['metrics']
        transfers = session_data['agent_transfers']
        
        # Calculate session duration
        start_time = datetime.fromisoformat(session_info['start_time'])
        end_time = datetime.fromisoformat(session_info['end_time']) if session_info['end_time'] else datetime.now()
        duration = end_time - start_time
        
        # Analyze conversation flow
        conversation_flow = []
        for transcript in transcripts:
            conversation_flow.append({
                'timestamp': transcript['timestamp'],
                'agent': transcript['agent_name'],
                'role': transcript['role'],
                'content': transcript['content'][:100] + "..." if len(transcript['content']) > 100 else transcript['content']
            })
        
        # Analyze agent transfers
        agent_path = [t['from_agent'] for t in transfers] + [transfers[-1]['to_agent']] if transfers else ['greeter']
        
        # Message statistics
        message_stats = {}
        for transcript in transcripts:
            role = transcript['role']
            message_stats[role] = message_stats.get(role, 0) + 1
        
        # Metrics summary
        metrics_summary = {}
        for metric in metrics:
            key = f"{metric['metric_type']}_{metric['metric_name']}"
            if key not in metrics_summary:
                metrics_summary[key] = []
            metrics_summary[key].append(metric['value'])
        
        # Calculate averages
        metrics_avg = {k: sum(v)/len(v) for k, v in metrics_summary.items()}
        
        return {
            'session_id': session_id,
            'start_time': session_info['start_time'],
            'end_time': session_info['end_time'],
            'duration_seconds': duration.total_seconds(),
            'status': session_info['status'],
            'customer_info': {
                'name': user_data['customer_name'] if user_data else None,
                'phone': user_data['customer_phone'] if user_data else None,
                'booking_date_time': user_data['booking_date_time'] if user_data else None,
                'booking_reason': user_data['booking_reason'] if user_data else None
            },
            'conversation_stats': {
                'total_messages': len(transcripts),
                'message_breakdown': message_stats,
                'agent_transfers': len(transfers),
                'agent_path': agent_path
            },
            'metrics_summary': metrics_avg,
            'conversation_flow': conversation_flow
        }
    
    async def get_sessions_by_date_range(self, date_from: datetime, date_to: datetime) -> List[Dict[str, Any]]:
        """Get sessions within a date range"""
        async with self.db_manager.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT s.*, u.customer_name, u.customer_phone, u.booking_date_time, u.booking_reason
                FROM sessions s
                LEFT JOIN user_data u ON s.id = u.session_id
                WHERE s.start_time >= ? AND s.start_time < ?
                ORDER BY s.start_time
            """, (date_from, date_to))
            
            sessions = await cursor.fetchall()
        
        return [dict(session) for session in sessions]
    
    async def get_daily_summary(self, date: datetime = None) -> Dict[str, Any]:
        """Get summary statistics for a specific day"""
        if date is None:
            date = datetime.now()
        
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        sessions = await self.get_sessions_by_date_range(start_of_day, end_of_day)
        
        total_sessions = len(sessions)
        completed_bookings = sum(1 for s in sessions if s['customer_name'] and s['customer_phone'])
        
        # Get all transcripts for the day
        transcripts_df = await self.get_transcripts_dataframe()
        if not transcripts_df.empty:
            day_transcripts = transcripts_df[
                (transcripts_df['timestamp'] >= start_of_day) & 
                (transcripts_df['timestamp'] < end_of_day)
            ]
            total_messages = len(day_transcripts)
            avg_session_length = day_transcripts.groupby('session_id').size().mean()
        else:
            total_messages = 0
            avg_session_length = 0
        
        return {
            'date': date.strftime('%Y-%m-%d'),
            'total_sessions': total_sessions,
            'completed_bookings': completed_bookings,
            'completion_rate': completed_bookings / total_sessions if total_sessions > 0 else 0,
            'total_messages': total_messages,
            'avg_session_length': avg_session_length,
            'sessions': sessions
        }
    
    async def get_customer_interaction_analysis(self) -> Dict[str, Any]:
        """Analyze customer interaction patterns"""
        transcripts_df = await self.get_transcripts_dataframe()
        
        if transcripts_df.empty:
            return {"error": "No transcript data available"}
        
        # Messages by role
        role_distribution = transcripts_df['role'].value_counts().to_dict()
        
        # Messages by agent
        agent_distribution = transcripts_df['agent_name'].value_counts().to_dict()
        
        # Average session length by successful vs unsuccessful bookings
        sessions_df = await self.get_sessions_dataframe()
        user_data_df = await self.get_user_data_dataframe()
        
        # Merge sessions with user data to identify successful bookings
        if not user_data_df.empty:
            sessions_with_user_data = sessions_df.merge(
                user_data_df, left_on='id', right_on='session_id', how='left'
            )
            successful_sessions = sessions_with_user_data[sessions_with_user_data['customer_name'].notna()]
            unsuccessful_sessions = sessions_with_user_data[sessions_with_user_data['customer_name'].isna()]
        else:
            successful_sessions = pd.DataFrame()
            unsuccessful_sessions = sessions_df
        
        return {
            'role_distribution': role_distribution,
            'agent_distribution': agent_distribution,
            'session_analysis': {
                'total_sessions': len(sessions_df),
                'successful_bookings': len(successful_sessions),
                'success_rate': len(successful_sessions) / len(sessions_df) if len(sessions_df) > 0 else 0,
                'avg_duration_successful': successful_sessions['duration_seconds'].mean() if not successful_sessions.empty else 0,
                'avg_duration_unsuccessful': unsuccessful_sessions['duration_seconds'].mean() if not unsuccessful_sessions.empty else 0
            }
        }
    
    async def export_session_transcript(self, session_id: str, format: str = 'txt') -> str:
        """Export a session transcript in readable format"""
        session_data = await self.db_manager.get_session_data(session_id)
        if not session_data:
            return "Session not found"
        
        transcripts = session_data['transcripts']
        user_data = session_data['user_data']
        
        output = []
        output.append(f"Session Transcript: {session_id}")
        output.append(f"Date: {session_data['session']['start_time']}")
        
        if user_data:
            output.append(f"Customer: {user_data['customer_name'] or 'Unknown'}")
            output.append(f"Phone: {user_data['customer_phone'] or 'Unknown'}")
            output.append(f"Booking: {user_data['booking_date_time'] or 'Unknown'}")
            output.append(f"Reason: {user_data['booking_reason'] or 'Unknown'}")
        
        output.append("\n" + "="*50)
        output.append("CONVERSATION TRANSCRIPT")
        output.append("="*50)
        
        for transcript in transcripts:
            timestamp = datetime.fromisoformat(transcript['timestamp']).strftime('%H:%M:%S')
            role = transcript['role'].upper()
            agent = transcript['agent_name']
            content = transcript['content']
            
            if role == 'USER':
                output.append(f"\n[{timestamp}] CUSTOMER: {content}")
            elif role == 'ASSISTANT':
                output.append(f"[{timestamp}] {agent.upper()}: {content}")
            elif role == 'SYSTEM':
                output.append(f"[{timestamp}] SYSTEM ({agent}): {content}")
            elif role == 'FUNCTION_CALL':
                output.append(f"[{timestamp}] FUNCTION ({agent}): {content}")
        
        return "\n".join(output)
    
    async def plot_session_metrics(self, session_id: str, save_path: str = None):
        """Generate plots for session metrics"""
        metrics_df = await self.get_metrics_dataframe(session_id)
        
        if metrics_df.empty:
            print("No metrics data available for this session")
            return
        
        # Set up the plot
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'Session Metrics: {session_id}', fontsize=16)
        
        # Plot 1: Metrics over time
        ax1 = axes[0, 0]
        for metric_type in metrics_df['metric_type'].unique():
            metric_data = metrics_df[metrics_df['metric_type'] == metric_type]
            ax1.plot(metric_data['timestamp'], metric_data['value'], 
                    label=metric_type, marker='o')
        ax1.set_title('Metrics Over Time')
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Value')
        ax1.legend()
        ax1.tick_params(axis='x', rotation=45)
        
        # Plot 2: Metric distribution
        ax2 = axes[0, 1]
        metric_counts = metrics_df['metric_type'].value_counts()
        ax2.pie(metric_counts.values, labels=metric_counts.index, autopct='%1.1f%%')
        ax2.set_title('Metric Type Distribution')
        
        # Plot 3: Average values by metric type
        ax3 = axes[1, 0]
        avg_metrics = metrics_df.groupby('metric_type')['value'].mean()
        ax3.bar(avg_metrics.index, avg_metrics.values)
        ax3.set_title('Average Values by Metric Type')
        ax3.set_xlabel('Metric Type')
        ax3.set_ylabel('Average Value')
        ax3.tick_params(axis='x', rotation=45)
        
        # Plot 4: Timeline of events
        ax4 = axes[1, 1]
        transcripts_df = await self.get_transcripts_dataframe(session_id)
        if not transcripts_df.empty:
            role_counts = transcripts_df['role'].value_counts()
            ax4.bar(role_counts.index, role_counts.values)
            ax4.set_title('Message Types')
            ax4.set_xlabel('Role')
            ax4.set_ylabel('Count')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
    
    async def get_performance_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Get performance metrics for the last N days"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        sessions = await self.get_sessions_by_date_range(start_date, end_date)
        
        # Calculate key metrics
        total_sessions = len(sessions)
        successful_bookings = sum(1 for s in sessions if s['customer_name'] and s['customer_phone'])
        
        # Average session duration
        completed_sessions = [s for s in sessions if s['end_time']]
        if completed_sessions:
            avg_duration = sum(
                (datetime.fromisoformat(s['end_time']) - datetime.fromisoformat(s['start_time'])).total_seconds()
                for s in completed_sessions
            ) / len(completed_sessions)
        else:
            avg_duration = 0
        
        # Daily breakdown
        daily_stats = {}
        for i in range(days):
            day = start_date + timedelta(days=i)
            day_sessions = [s for s in sessions if 
                          datetime.fromisoformat(s['start_time']).date() == day.date()]
            daily_stats[day.strftime('%Y-%m-%d')] = {
                'sessions': len(day_sessions),
                'successful': sum(1 for s in day_sessions if s['customer_name'])
            }
        
        return {
            'period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            'total_sessions': total_sessions,
            'successful_bookings': successful_bookings,
            'success_rate': successful_bookings / total_sessions if total_sessions > 0 else 0,
            'avg_session_duration': avg_duration,
            'daily_breakdown': daily_stats
        }
    
    async def get_agent_performance_analysis(self) -> Dict[str, Any]:
        """Analyze agent performance metrics"""
        transcripts_df = await self.get_transcripts_dataframe()
        
        if transcripts_df.empty:
            return {"error": "No transcript data available"}
        
        # Messages per agent
        agent_stats = transcripts_df.groupby('agent_name').agg({
            'id': 'count',
            'session_id': 'nunique'
        }).rename(columns={'id': 'total_messages', 'session_id': 'unique_sessions'})
        
        # Average messages per session by agent
        agent_stats['avg_messages_per_session'] = agent_stats['total_messages'] / agent_stats['unique_sessions']
        
        # Get transfer data
        async with self.db_manager.get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM agent_transfers ORDER BY timestamp")
            transfers = await cursor.fetchall()
        
        # Analyze transfer patterns
        transfer_stats = {}
        for transfer in transfers:
            from_agent = transfer['from_agent']
            to_agent = transfer['to_agent']
            
            if from_agent not in transfer_stats:
                transfer_stats[from_agent] = {'transfers_out': 0, 'transfers_in': 0}
            if to_agent not in transfer_stats:
                transfer_stats[to_agent] = {'transfers_out': 0, 'transfers_in': 0}
            
            transfer_stats[from_agent]['transfers_out'] += 1
            transfer_stats[to_agent]['transfers_in'] += 1
        
        return {
            'agent_message_stats': agent_stats.to_dict('index'),
            'transfer_patterns': transfer_stats,
            'total_transfers': len(transfers)
        }
    
    async def close(self):
        """Close the database manager"""
        await self.db_manager.stop_background_processing()


# Async helper functions
async def print_session_report(session_id: str):
    """Print a formatted session report"""
    analyzer = AsyncDataAnalyzer()
    try:
        report = await analyzer.generate_session_report(session_id)
        
        print(f"\n{'='*60}")
        print(f"SESSION REPORT: {session_id}")
        print(f"{'='*60}")
        
        if "error" in report:
            print(f"Error: {report['error']}")
            return
        
        print(f"Start Time: {report['start_time']}")
        print(f"Duration: {report['duration_seconds']:.1f} seconds")
        print(f"Status: {report['status']}")
        
        print(f"\nCustomer Information:")
        customer = report['customer_info']
        print(f"  Name: {customer['name'] or 'Not provided'}")
        print(f"  Phone: {customer['phone'] or 'Not provided'}")
        print(f"  Booking Date: {customer['booking_date_time'] or 'Not provided'}")
        print(f"  Reason: {customer['booking_reason'] or 'Not provided'}")
        
        print(f"\nConversation Statistics:")
        stats = report['conversation_stats']
        print(f"  Total Messages: {stats['total_messages']}")
        print(f"  Agent Transfers: {stats['agent_transfers']}")
        print(f"  Agent Path: {' -> '.join(stats['agent_path'])}")
        
        if report['metrics_summary']:
            print(f"\nMetrics Summary:")
            for metric, value in report['metrics_summary'].items():
                print(f"  {metric}: {value:.3f}")
    
    finally:
        await analyzer.close()

async def list_recent_sessions(days: int = 7):
    """List recent sessions"""
    analyzer = AsyncDataAnalyzer()
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        sessions = await analyzer.get_sessions_by_date_range(start_date, end_date)
        
        print(f"\n{'='*80}")
        print(f"RECENT SESSIONS (Last {days} days)")
        print(f"{'='*80}")
        
        for session in sessions:
            status = "✓" if session['customer_name'] else "✗"
            print(f"{status} {session['id'][:8]}... | {session['start_time'][:19]} | {session['customer_name'] or 'Unknown'}")
    
    finally:
        await analyzer.close()

async def show_performance_dashboard(days: int = 7):
    """Show a performance dashboard"""
    analyzer = AsyncDataAnalyzer()
    try:
        # Get performance metrics
        metrics = await analyzer.get_performance_metrics(days)
        
        print(f"\n{'='*60}")
        print(f"PERFORMANCE DASHBOARD (Last {days} days)")
        print(f"{'='*60}")
        
        print(f"Period: {metrics['period']}")
        print(f"Total Sessions: {metrics['total_sessions']}")
        print(f"Successful Bookings: {metrics['successful_bookings']}")
        print(f"Success Rate: {metrics['success_rate']:.1%}")
        print(f"Average Session Duration: {metrics['avg_session_duration']:.1f} seconds")
        
        print(f"\nDaily Breakdown:")
        for date, stats in metrics['daily_breakdown'].items():
            success_rate = stats['successful'] / stats['sessions'] if stats['sessions'] > 0 else 0
            print(f"  {date}: {stats['sessions']} sessions, {stats['successful']} successful ({success_rate:.1%})")
        
        # Get agent performance
        agent_performance = await analyzer.get_agent_performance_analysis()
        if "error" not in agent_performance:
            print(f"\nAgent Performance:")
            for agent, stats in agent_performance['agent_message_stats'].items():
                print(f"  {agent}: {stats['total_messages']} messages across {stats['unique_sessions']} sessions")
                print(f"    Avg messages per session: {stats['avg_messages_per_session']:.1f}")
        
        # Get customer interaction analysis
        interaction_analysis = await analyzer.get_customer_interaction_analysis()
        if "error" not in interaction_analysis:
            print(f"\nInteraction Analysis:")
            session_analysis = interaction_analysis['session_analysis']
            print(f"  Overall Success Rate: {session_analysis['success_rate']:.1%}")
            print(f"  Avg Duration (Successful): {session_analysis['avg_duration_successful']:.1f}s")
            print(f"  Avg Duration (Unsuccessful): {session_analysis['avg_duration_unsuccessful']:.1f}s")
    
    finally:
        await analyzer.close()


# Example usage
async def main():
    """Example usage of the async data analyzer"""
    # Show recent sessions
    await list_recent_sessions(7)
    
    # Show performance dashboard
    await show_performance_dashboard(7)
    
    # Example: Get a specific session report
    # await print_session_report("your-session-id-here")


if __name__ == "__main__":
    asyncio.run(main())