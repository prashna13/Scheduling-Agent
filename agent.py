"""
Entrypoint for Saathi Sneha Care LangChain Scheduling Agent.
Equipped strictly with the 4 core tools:
1. read_availability
2. check_conflict
3. propose_slot
4. write_booking
"""
from langchain_agent import (
    ask_agent,
    CORE_TOOLS,
    read_availability_tool,
    check_conflict_tool,
    propose_slot_tool,
    write_booking_tool,
    get_langchain_agent_executor,
    fallback_answer_query
)

if __name__ == "__main__":
    print("Saathi Sneha Care Scheduling Agent initialized with 4 core tools.")
    response = ask_agent("Is Nurse Sunita Rao free on 2026-09-24?")
    print(response)
