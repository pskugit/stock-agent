from portfolio import Portfolio, Position, Transaction

from jinja2 import Template
import faiss

from typing import Optional

from news import NewsApiCustomClient, WorldNewsCustomClient
from datetime import datetime
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path

from memory.memorymodel import Episode, Experience, Reflection
from memory.stores import MemoryController

# Flow 1 Prompt: "Learning"
flow_1_prompt_template = Template(
    "You are a trading bot...\n\n"
    "Your goal is ...\n"
    "Your current plan is\n"
    "You make memories while trading ...\n\n"
    "Your latest memory is\n"
    "{{latest_memory}}\n\n"
    "Your current state is\n"
    "{{portfolio}}\n"
    "{{transaction_history}}\n\n"
    "You are now given the opportunity to reflect on your action. To do so, you must verbalize:\n"
    "- An evaluation of your previous expectation: Given the now available information of your portfolio's development, "
    "ask yourself: 'Did things happen in the way you predicted them?'\n"
    "- A learning: A short statement that draws a conclusion from the experience that may be helpful for similar future situations.\n\n"
    "Provide your answer in this JSON format:\n"
    "{\n"
    "    \"evaluation\": str,\n"
    "    \"learning\": str\n"
    "}"
)


# Flow 2 Prompt: "Trading"
flow_2_prompt_template = Template(
    "You are a trading bot...\n"
    "It is {{ current_date.strftime('%A, %d of %B') }}\n"
    "Keep in mind the weekend as the exchanges are closed on Saturday and Sunday. "
    "As such, we do not expect any price changes during those days.\n\n"
    "Your goal is ...\n"
    "Your current plan is\n"
    "You make memories while trading ...\n\n"
    "Your current state is\n"
    "{{portfolio}}\n"
    "{{transaction_history}}\n\n"
    "You are currently trading on these symbols\n"
    "{{symbols_of_interest}}\n\n"
    "Today's news summaries for the symbols:\n"
    "{{news_summaries}}\n\n"
    "With regard to the latest news, you remember the following experiences, "
    "which you - at the time - had also reflected upon and drew some learnings:\n"
    "{{memories}}\n\n"
    "Today, you already did the following trades:\n\n"
    "You may now choose your next action:\n"
    "- buy symbol :: see tool description\n"
    "- sell symbol :: see tool description\n"
    "- wait :: see tool description\n\n"
    "When selling or buying stocks, keep in mind some price fluctuation. "
    "A request to sell 100€ of a 100€ position may not be filled "
    "if the position's value has suddenly decreased by a bit in the meantime.\n"
    "You can always close positions safely via close_position."
)



# Start Flow 1

# for symbol in tracked symbols
example_episode = {
  "date": "2024-01-21T10:00:00Z",
  "news_of_the_day": "Tech stocks rally after strong earnings reports.",
  "initial_position": None,
  "action": {
    "type": "BUY",
    "symbol": "GOOGL",
    "price": 2800.00,
    "amount": 2,
    "total": 5600.00
  },
  "posterior_position": {
    'symbol': 'GOOGL',
    'total_position_value': 3999.9999999999995,
    'last_update_price': 221.93,
    'quantity': 18.02370116703465,
    "buy_in_price": 2800.00,
    'absolute_change_since_start': 0.0,
    'relative_change_since_start': 0.0,
  },
  "expectation": "GOOGL stock will rise after the new AI product announcement.",
  "expectation_evaluation_horizon": "7 days",
  "developed_position": {
    "Symbol": "GOOGL",
    "price": 2600.00,
    "amount": 2,
    "total": 5200.00,
    "buy_in_price": 2800.00,
    "gain": -400.00
  },
  "expectation_evaluation": "GOOGL stock dropped 7.1% due to negative market sentiment despite the product announcement.",
  "learning": "Market reactions to product announcements can be overshadowed by broader economic factors. Future strategies should account for overall market sentiment rather than focusing solely on company-specific news."
}

    
action_flow_tools = [
    {
        "type": "function",
        "function": {
            "name": "buy",
            "description": "Buys 'buy_value' worth of a given symbol/stock. The order will be executed at "
                           "current market price and the resulting number (or fraction) of shares will be added to your portfolio. "
                           "The amount paid for the purchase (equivalent to the 'buy_value') will be deducted from your cash account. "
                           "The action will fail if you do not have sufficient cash funds. "
                           "You must also provide an explanation of your decision in the form of an 'expectation'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Any valid stock trading symbol (e.g., AAPL for Apple)."
                    },
                    "buy_value": {
                        "type": "number",
                        "description": "Amount to be invested. Your currency is Euro, and the minimum amount is 1€."
                    },
                    "expectation": {
                        "type": "string",
                        "description": "Short text to explain why you choose to buy. Write the expectation in a way that it can be evaluated in the future to determine if it was correct or wrong."
                    }
                },
                "required": ["symbol", "buy_value", "expectation"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sell",
            "description": "Sells 'sell_value' worth of a given symbol/stock. The order will be executed at "
                           "current market price, and the resulting number (or fraction) of shares will be removed from your portfolio. "
                           "The amount gained from the sale (equivalent to the 'sell_value') will be added to your cash account. "
                           "The action will fail if you do not hold a sufficiently large position of the symbol you aim to sell. "
                           "You must also provide an explanation of your decision in the form of an 'expectation'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Any valid stock trading symbol (e.g., AAPL for Apple)."
                    },
                    "sell_value": {
                        "type": "number",
                        "description": "Amount to be invested. Your currency is Euro, and the minimum amount is 1€."
                    },
                    "expectation": {
                        "type": "string",
                        "description": "Short text to explain why you choose to sell. Write the expectation in a way that it can be evaluated in the future to determine if it was correct or wrong."
                    }
                },
                "required": ["symbol", "sell_value", "expectation"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wait",
            "description": "You are done trading for the day and decide not to take another BUY or SELL action. "
                        "This function shall be called whenever your portfolio does not need any changes at that moment.",
            "parameters": {} 
        }
    }
]

        

    
    
class Agent:
    def __init__(self, config_path: str):
        """
        Initialize agent state from a YAML config file.
        
        Args:
            config_path: Path to the agent state YAML file
        """
        self.config_path = Path(config_path)
        self.portfolio = None
        self.current_episode = None
        self.memory_controller = None   
        self.state_data = self.load_state()
        self.news_client = NewsApiCustomClient()
        self.world_news_client = WorldNewsCustomClient()
        
        
    def load_state(self) -> Dict[str, Any]:
        """Load the agent state from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
            
        with open(self.config_path, 'r') as f:
            state = yaml.safe_load(f)
            
        # Load associated portfolio if exists
        portfolio_path = Path(state['files']['portfolio'])
        if portfolio_path.exists():
            self.portfolio = Portfolio.from_file(str(portfolio_path))
        
        # Load associated memory data if exists
        if portfolio_path.exists():
            self.memory_controller = MemoryController(agent_name=state['agent_config']['name'])
        
        print(f"Agent: loaded state from {self.config_path} as {state}")
        return state
    
    def save_state(self):
        """Save the current state to YAML file."""
        # Update metrics
        self.state_data['last_run'] = datetime.now().isoformat()
        self.state_data['metrics']['memories'] = len(self.memory_controller.memory_index.db)
        self.state_data['metrics']['current_portfolio_value'] = self.portfolio.total_value
        self.state_data['metrics']['total_trades'] = len(self.portfolio.transaction_history)

        # Save main state file
        with open(self.config_path, 'w') as f:
            yaml.dump(self.state_data, f, default_flow_style=False, sort_keys=False)
            
        # Save portfolio if it exists
        self.portfolio.to_file(self.state_data['files']['portfolio'])
    
    @property
    def agent_name(self) -> str:
        """Get agent name."""
        return self.state_data['agent_config']['name']
    
    @property
    def symbols_of_interest(self) -> List[str]:
        """Get list of symbols the agent is interested in."""
        return self.state_data['symbols_of_interest']
    
    @property
    def file_paths(self) -> Dict[str, str]:
        """Get dictionary of all file paths."""
        return self.state_data['files']
    
    def get_metric(self, metric_name: str) -> Optional[Any]:
        """Get a specific metric value."""
        return self.state_data.get('metrics', {}).get(metric_name)
    
    def update_metric(self, metric_name: str, value: Any):
        """Update a specific metric value."""
        if 'metrics' not in self.state_data:
            self.state_data['metrics'] = {}
        self.state_data['metrics'][metric_name] = value
    
    def update_portfolio_metrics(self):
        """Update portfolio-related metrics based on current portfolio state."""
        if self.portfolio:
            self.update_metric('current_portfolio_value', self.portfolio.portfolio_value)
    
    @classmethod
    def create_new(cls, 
                  base_path: str, 
                  agent_name: str, 
                  initial_portfolio_value: float = 1000.0,
                  symbols: List[str] = None) -> 'Agent':
        """
        Create a new agent state with default configuration.
        
        Args:
            base_path: Base directory for the agent
            agent_name: Name of the agent
            initial_portfolio_value: Starting portfolio value
            symbols: List of symbols of interest
        """
        # Create agent directory
        agent_dir = Path(base_path) / agent_name
        agent_dir.mkdir(parents=True, exist_ok=True)
        
        # Create state configuration
        state_config = {
            'version': '1.0',
            'created_at': datetime.now().isoformat(),
            'last_run': datetime.now().isoformat(),
            'agent_config': {
                'name': agent_name
            },
            'files': {
                'portfolio': str(agent_dir / 'portfolio.json'),
                'memory_index': str(agent_dir / 'memory_index.json'),
                'memory_embeddings': str(agent_dir / 'faiss_index.bin'),
                'current_episode_store': str(agent_dir / 'current_episode_store.json')
            },
            'symbols_of_interest': symbols or ['AAPL', 'GOOGL', 'MSFT'],
            'metrics': {
                'total_trades': 0,
                'memories': 0,
                'current_portfolio_value': initial_portfolio_value,
                'start_portfolio_value': initial_portfolio_value
            }
        }
        
        # Save state configuration
        config_path = agent_dir / 'agent_state.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(state_config, f, default_flow_style=False, sort_keys=False)
        
        # Create and save initial portfolio
        portfolio = Portfolio()
        portfolio.load_cash(initial_portfolio_value)
        portfolio.to_file(state_config['files']['portfolio'])
        
        # Return new agent state instance
        return cls(str(config_path))
        
        
    def action(self):
        pass
        
        # get news summary
        
        # create new episode 
        
        # get similar episodes
        
        # choose action
        
        # run action
        
        # save current episode
        
    
    def reflection(self):
        pass
        
        # update portfolio
        
        # get latest experience
        
        # evaluate experience
        
        # update experience in index
        
        # create and save embeddings of experience
        
        
    def run(self):
        self.reflection()
        self.action()





# Usage example:
if __name__ == "__main__":
    # Create a new agent
    agent_state = Agent.create_new(
        base_path="agents",
        agent_name="agent01",
        initial_portfolio_value=1000.0,
        symbols=["AAPL", "GOOGL", "MSFT"]
    )
    
    # Or load existing agent
    # agent_state = Agent("agents/agent01/agent_state.yaml")
    
    # Access properties
    print(f"Agent: {agent_state.agent_name}")
    print(f"Symbols: {agent_state.symbols_of_interest}")
    print(f"Portfolio value: {agent_state.get_metric('current_portfolio_value')}")
    
    # Update metrics
    agent_state.update_metric("total_trades", 1)
    agent_state.update_portfolio_metrics()
    
    # Save state
    agent_state.save_state()
        
        
        

