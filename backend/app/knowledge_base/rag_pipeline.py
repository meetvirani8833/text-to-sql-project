from typing import List, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from app.dependencies import get_llm

def generate_table_explanation(table_name: str, column_info: List[Dict[str, Any]], user_description: str) -> str:
    """
    Generates a concise table explanation using LLM.
    """
    llm = get_llm()
    
    # Format column info for prompt
    columns_text = "\n".join([
        f"- {col['name']} ({col['type']}): {col.get('comment', '')}" 
        for col in column_info
    ])
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a database documentation expert."),
        ("human", """Given the table '{table_name}' with the following columns:
{columns_text}

And this user-provided description: 
"{user_description}"

Generate a concise 2-3 sentence explanation of what this table stores, its purpose in a university curriculum database, and key relationships.
Explanation:""")
    ])
    
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({
        "table_name": table_name,
        "columns_text": columns_text,
        "user_description": user_description or "No description provided."
    })

def generate_column_explanations(table_name: str, table_explanation: str, columns: List[Dict[str, Any]], user_descriptions: Dict[str, str]) -> List[Dict[str, str]]:
    """
    Generates explanations for a list of columns.
    """
    llm = get_llm()
    
    # We can batch this or do it loop. For better context, let's do one by one or small batches.
    # To save tokens/calls, we could try to do it in one go if the table isn't too huge.
    # The prompt asks for "For each column...". Let's iterate for now to be safe and accurate.
    
    results = []
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are a database documentation expert."),
        ("human", """Given table '{table_name}' which is described as:
{table_explanation}

Explain what the column '{col_name}' (type: {data_type}) stores.
User context: {user_desc}

Be concise - one sentence explanation.
Explanation:""")
    ])
    
    chain = prompt_template | llm | StrOutputParser()
    
    for col in columns:
        col_name = col['name']
        user_desc = user_descriptions.get(col_name, "No description provided.")
        
        explanation = chain.invoke({
            "table_name": table_name,
            "table_explanation": table_explanation,
            "col_name": col_name,
            "data_type": col['type'],
            "user_desc": user_desc
        })
        
        results.append({
            "column_name": col_name,
            "explanation": explanation
        })
        
    return results
