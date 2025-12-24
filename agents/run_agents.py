import asyncio
import signal
import sys
from shared.config.settings import settings
from shared.utils.logging_config import get_logger, setup_logging
from agents.intake_agent.agent import IntakeAgent
setup_logging(
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_to_console=settings.log_to_console
    )
logger = get_logger(__name__)

class AgentOrchestrator:
    """Orchestrates the running of various agents."""
    
    def __init__(self):
        self.shutdown_event = asyncio.Event()
        self.agents: list[asyncio.Task] = []


    def setup_signal_handlers(self):
        """Register signal handlers for graceful shutdown."""
        def handle_shutdown(sig, frame):
            sig_name = signal.Signals(sig).name
            logger.info(f"Received {sig_name}, initiating graceful shutdown...")
            self.shutdown_event.set()
        
        signal.signal(signal.SIGINT, handle_shutdown)   # Ctrl+C
        signal.signal(signal.SIGTERM, handle_shutdown)  # kill command
        
        # Windows compatibility
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, handle_shutdown)

    async def run_agent(self, agent_class, name: str):
        """Run a single agent with error handling."""
        logger.info(f"Starting {name}...")
        
        try:
            agent = agent_class(
                shutdown_event=self.shutdown_event
            )
            await agent.run()
            
        except asyncio.CancelledError:
            logger.info(f"{name} cancelled")
        except Exception as e:
            logger.error(f"{name} failed: {e}", exc_info=True)
        finally:
            logger.info(f"{name} stopped")

    async def start_all_agents(self):
        """Start all agents as concurrent tasks."""
        agent_configs = [
            (IntakeAgent, "IntakeAgent"),
            # (ValidationAgent, "ValidationAgent"),
            # (BudgetAgent, "BudgetAgent"),
            # (ApprovalAgent, "ApprovalAgent"),
            # (PaymentAgent, "PaymentAgent"),
            # (AnalyticsAgent, "AnalyticsAgent"),
        ]
        
        for agent_class, name in agent_configs:
            task = asyncio.create_task(
                self.run_agent(agent_class, name),
                name=name
            )
            self.agents.append(task)
        
        logger.info(f"Started {len(self.agents)} agents")


    async def wait_for_shutdown(self):
        """Wait for shutdown signal."""
        await self.shutdown_event.wait()
        logger.info("Shutdown signal received, stopping agents...")
    
    async def stop_all_agents(self, timeout: float = 30.0):
        """Stop all agents gracefully with timeout."""
        if not self.agents:
            return
        
        logger.info(f"Waiting up to {timeout}s for agents to finish...")
        
        try:
            # Wait for agents to stop naturally
            await asyncio.wait_for(
                asyncio.gather(*self.agents, return_exceptions=True),
                timeout=timeout
            )
            logger.info("All agents stopped gracefully")
            
        except asyncio.TimeoutError:
            logger.warning("Timeout exceeded, forcing agent shutdown...")
            
            # Cancel remaining tasks
            for task in self.agents:
                if not task.done():
                    task.cancel()
            
            # Wait for cancellations to complete
            await asyncio.gather(*self.agents, return_exceptions=True)
            logger.info("All agents forcefully stopped")
    
    async def run(self):
        """Main orchestrator loop."""
        self.setup_signal_handlers()
        
        try:
            # Start all agents
            await self.start_all_agents()
            
            # Wait for shutdown signal
            await self.wait_for_shutdown()
            
            # Stop all agents gracefully
            await self.stop_all_agents()
            
        except Exception as e:
            logger.error(f"Orchestrator error: {e}", exc_info=True)
            raise
        finally:
            logger.info("Orchestrator shutdown complete")



async def main():
    """Entry point."""
    orchestrator = AgentOrchestrator()
    await orchestrator.run()



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)