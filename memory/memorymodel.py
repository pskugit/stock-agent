from pydantic import BaseModel
from portfolio import Portfolio, Position, Transaction

from typing import Optional

from datetime import datetime
from typing import Optional

from uuid import uuid4

class Perception(BaseModel):
    news_of_the_day: str
    portfolio: Portfolio
    
class Action(BaseModel):
    action_type: str
    transaction: Optional[Transaction] = None
    expectation: str

class Experience(BaseModel):
    date: datetime
    perception: Perception
    action: Optional[Action] = None

    def __str__(self):
        parts = [
            f"Date:\n {self.date.strftime('%Y-%m-%d %H:%M:%S')}",
            f"News of the Day:\n {self.perception.news_of_the_day}",
            f"Action:\n {self.action.action_type if self.action else "None"}",
            f"Transaction:\n {str(self.action.transaction) if (self.action and self.action.transaction) else 'None'}",
            f"{str(self.perception.portfolio).replace("\n","\n ")}",
            f"Expectation:\n {self.action.expectation if self.action else "None"}",
        ]
        return "\n\n".join(parts)

class Reflection(BaseModel):
    posterior_position: Optional[Position] = None
    expectation_evaluation: str
    learning: str

    def __str__(self):
        parts = [
            f"Posterior Position:\n {str(self.posterior_position) if self.posterior_position else 'None'}",
            f"Expectation Evaluation:\n {self.expectation_evaluation}",
            f"Learning:\n {self.learning}",
        ]
        return "\n\n".join(parts)

class Episode(BaseModel):
    unique_id: str = str(uuid4())
    experience: Experience
    reflection: Optional[Reflection] = None
        
    def __str__(self):
        parts = [
            "EXPERIENCE:",
            str(self.experience),
            "REFLECTION:",
            str(self.reflection) if self.reflection else "None",
        ]
        return "\n\n".join(parts)
    
    @classmethod
    def get_dummy(cls, portfolio=None, with_reflection=True):
        if portfolio is None:
            portfolio = Portfolio()
            portfolio.load_cash(10000)
            portfolio.buy("GOOGL", 4000)
            portfolio.sell("GOOGL", 1000)
            portfolio.buy("AAPL", 4000)
        
        experience = Experience(date=datetime.now(),
           news_of_the_day="Tech stocks rally after strong earnings reports.",
           action_type="BUY",
           transaction=portfolio.transaction_history[-1],
           portfolio=portfolio,
           expectation="AAPL stock will rise after the new AI product announcement.")
        
        if with_reflection:
            reflection = Reflection(posterior_position=portfolio.positions[list(portfolio.positions)[0]],
                            expectation_evaluation="AAPL stock stayed on the same level in the course of 24h, disregarding the new product announcement.",
                            learning="New product launches do not affect the market in a short timespan.")
            return cls(experience=experience,
                    reflection=reflection)
        else:
            return cls(experience=experience)