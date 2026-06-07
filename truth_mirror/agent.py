"""
ReAct Agent — optional component, not in critical path.
Enable via ENABLE_REACT_AGENT=true in .env.
Only activate with models >= 7B parameters.
Recommended: llama3.1:8b or larger.
"""
import re
import logging
from typing import Callable, Dict, Any

from truth_mirror.llm_client import LLMClient

logger = logging.getLogger(__name__)

class ReActAgent:
    """
    A custom ReAct (Reason + Act) Agent framework.
    Uses the LLMClient for completions and a dictionary of tools.
    """
    def __init__(self, llm_client: LLMClient, tools: Dict[str, Callable], max_iterations: int = 10):
        self.llm_client = llm_client
        self.tools = tools
        self.max_iterations = max_iterations
        
        self.system_prompt = """You are a strictly formatted ReAct reasoning agent.
You have access to the following tools:
{tools_desc}

You MUST use the exact format below for every single step.

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat multiple times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

EXAMPLE:
Question: Did humans land on Mars?
Thought: I need to decompose this and verify the subclaims.
Action: decompose_claim
Action Input: Did humans land on Mars?
Observation: ["Humans landed on Mars"]
Thought: Now I need to verify the subclaim.
Action: verify_subclaim
Action Input: Humans landed on Mars
Observation: Status: Contradicted, Confidence: 0.99. Sources: 12.
Thought: I now know the final answer.
Final Answer: The claim is contradicted.

Always finish with "Final Answer:" when you have resolved the question. Do not skip steps.
"""

    def _build_system_prompt(self) -> str:
        tools_desc = "\n".join([f"- {name}: {getattr(func, '__doc__', 'No description available').strip()}" for name, func in self.tools.items()])
        tool_names = ", ".join(self.tools.keys())
        return self.system_prompt.format(tools_desc=tools_desc, tool_names=tool_names)

    def run(self, question: str) -> str:
        """
        Runs the ReAct loop until a Final Answer is reached or max_iterations is hit.
        """
        prompt = self._build_system_prompt() + f"\nQuestion: {question}\n"
        
        for i in range(self.max_iterations):
            logger.info(f"ReAct Iteration {i+1}/{self.max_iterations}")
            
            try:
                response = self.llm_client.complete(prompt)
            except Exception as e:
                logger.error(f"LLM completion failed: {e}")
                return f"Error: LLM completion failed with {e}"
                
            prompt += response + "\n"
            
            if "Final Answer:" in response:
                final_answer = response.split("Final Answer:", 1)[1].strip()
                return final_answer
            
            # Extract Action and Action Input using regex
            action_match = re.search(r"Action:\s*(.*?)(?:\n|$)", response)
            action_input_match = re.search(r"Action Input:\s*(.*?)(?:\n|$)", response)
            
            if action_match and action_input_match:
                action = action_match.group(1).strip()
                action_input = action_input_match.group(1).strip()
                
                if action in self.tools:
                    try:
                        observation = str(self.tools[action](action_input))
                    except Exception as e:
                        observation = f"Error executing tool '{action}': {e}"
                else:
                    observation = f"Error: '{action}' is not a valid tool. Valid tools are: {list(self.tools.keys())}"
                    
                prompt += f"Observation: {observation}\n"
            else:
                # If the agent didn't output an action or final answer, prompt it to continue
                prompt += "Observation: You did not provide a valid Action and Action Input, or a Final Answer. Please follow the format.\n"
                
        return "Max iterations reached without finding a Final Answer."
