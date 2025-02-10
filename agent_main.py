from portfolio import Portfolio, Position, Transaction

from jinja2 import Template
import faiss
import inspect
from typing import Optional
import json
from news import NewsApiCustomClient, WorldNewsCustomClient
from datetime import datetime
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path

from memory.memorymodel import Episode, Experience, Reflection, ReflectionOutput, Perception, Action, ActionType
from memory.stores import MemoryController
from llm_utils import query_llm_with_tools, query_llm_with_structured_output

setting_prompt = str("You are a trading bot and financial expert.\n\n"
    "Your goal is to maximize your portfolio's value.\n"
    "Your current plan is: Buy shares when the news indicate a good buying opportunity, sell shares when the news indicate upcoming falling prices.\n"
    "You make memories while trading. Each memory contains two parts:"
    "the 'Experience'-part encompassing"
    "(A1) the news of the day"
    "(A2) the trading decision you made [BUY, SELL, WAIT]"
    "(A3) your portfolio at the time (after executing the trading decision)"
    "(A4) a statement on your expectations at the time\n\n"
    "Additionally a memory has a 'Reflection'-part encompassing"
    "(B1) an evaluation of your expectation at a later timestamp"
    "(B2) a learning, drawn from comparing the expectation with it's evaluation. The goal is to draw helpful learnings that increase your trading abilities in the future")
    
# Flow 1 Prompt: "Learning" = run_reflection
flow_1_prompt_template = Template(
    "{{setting_prompt}}"
    "You are now given the opportunity to reflect on your latest action."
    "Your latest memory's 'Experience'-part is\n"
    "{{latest_memory}}\n\n"
    "Today's state of your Portfolio is\n"
    "{{portfolio}}\n"
    "{{transaction_history}}\n\n"
    "You must now verbalize the following to complete the memory's 'Reflection'-part:\n"
    "- An evaluation of your previous expectation: Given the now available information of your portfolio's development, "
    "ask yourself: 'Did things happen in the way you predicted them?'\n"
    "- A learning: A short statement that draws a conclusion from the experience that may be helpful for similar future situations.\n\n"
    "Provide your answer in this JSON format:\n"
    "{\n"
    "    \"evaluation\": str,\n"
    "    \"learning\": str\n"
    "}"
)

# Flow 2 Prompt: "Trading" = run_action
flow_2_prompt_template = Template(
    "{{setting_prompt}}"
    "It is {{ current_date.strftime('%A, %d of %B') }}\n"
    "Keep in mind the weekend as the exchanges are closed on Saturday and Sunday. "
    "As such, we do not expect any price changes during those days.\n\n"
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
            "strict": True,
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
            "strict": True,
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
            "parameters": {
                "type": "object",
                "properties": {
                    "expectation": {
                        "type": "string",
                        "description": "Short text to explain why you choose to wait. Write the expectation in a way that it can be evaluated in the future to determine if it was correct or wrong."
                    }
                },
                "required": ["expectation"],
                "additionalProperties": False
            }
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
        self.state_data['metrics']['portfolio_value'] = self.portfolio.portfolio_value
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
            self.update_metric('portfolio_value', self.portfolio.portfolio_value)
    
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
                'portfolio_value': initial_portfolio_value,
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
        
    def execute_tool_call(self, completion) -> Action:
        tool_calls = completion.choices[0].message.tool_calls
        if not tool_calls:
            raise ValueError("No tool calls found in completion response.")
        
        tool_call = tool_calls[0]
        method_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        method = getattr(self.portfolio, method_name)
        sig = inspect.signature(method)
        valid_args = {k: v for k, v in args.items() if k in sig.parameters}
        transaction = method(**valid_args)

        action = Action(action_type=ActionType.from_str(method_name),
                        transaction=transaction,
                        expectation=args["expectation"])
        return action


    def run_action(self):
        print("-Action-")
        # get news summary
        news = self.news_client.get_daily_news_summary("AAPL")
        news += "\n"+self.world_news_client.get_daily_news_summary("AAPL")
        print(f"Retrieved news: {news[:100]}...(truncated)")
        
        # create new episode 
        experience = Experience(date=datetime.now(),
                        perception= Perception(
                            news_of_the_day=news,
                            portfolio=self.portfolio,
                        ))
        episode = Episode(experience=experience)
        
        # get similar episodes
        similar_episodes = self.memory_controller.get_similar_episodes(episode, best_k=1) 
        similar_episodes_str = "\n".join([f"Memory {i+1}:\n{s}" for i, s in enumerate(similar_episodes)]) if similar_episodes else "no memories yet"
        print(f"Retrieved similar episodes: {similar_episodes_str[:100]}...(truncated)")
        
        # choose action
        flow_2_prompt = flow_2_prompt_template.render(setting_prompt=setting_prompt,
                    current_date=datetime.now(),
                    portfolio=str(self.portfolio),
                    transaction_history = str(self.portfolio.transaction_history),
                    symbols_of_interest = str(self.symbols_of_interest),
                    news_summaries = news,
                    memories = similar_episodes_str)
        
        completion, cost = query_llm_with_tools(flow_2_prompt, tools=action_flow_tools)
        
        # run action
        action = self.execute_tool_call(completion)
        print(f"Chose action: {str(action.action_type)}")

        # save current episode
        episode.experience.action = action
        self.memory_controller.save_current_episode(episode)
        print(f"Saved current episode:\n{str(episode)}")
        
        self.save_state()
        
        
    def run_reflection(self):
        pass
        print("-Reflection-")
        # update portfolio
        self.portfolio.update()

        # get latest experience
        episode = self.memory_controller.get_current_episode()
        if not episode:
            print("No current episode to reflect upon")
            return
        print(f"Loaded current episode")

        # evaluate experience
        flow_1_prompt = flow_1_prompt_template.render(setting_prompt=setting_prompt,
                            latest_memory=str(episode),
                            portfolio=str(self.portfolio),
                            transaction_history = str(self.portfolio.transaction_history))
        
        completion, cost = query_llm_with_structured_output(flow_1_prompt, response_format=ReflectionOutput)
        print(f"Generated reflection")

        # instanciate reflection object
        posterior_position = self.portfolio.positions.get(episode.experience.action.transaction.symbol) if episode.experience.action.transaction else None
        reflection = Reflection(posterior_position=posterior_position,
                        expectation_evaluation=completion.expectation_evaluation,
                        learning=completion.learning)
        
        episode.reflection = reflection

        # create and save embeddings of finished episode
        self.memory_controller.save_finished_episode(episode)
        print(f"Saved finished episode:\n{str(episode)}")

        
    def run(self):
        self.run_reflection()
        self.run_action()





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
    print(f"Portfolio value: {agent_state.get_metric('portfolio_value')}")
    
    # Update metrics
    agent_state.update_metric("total_trades", 1)
    agent_state.update_portfolio_metrics()
    
    # Save state
    agent_state.save_state()
        
        
        

