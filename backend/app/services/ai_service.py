# import os
# import httpx
# from dotenv import load_dotenv

# RAG_QUERY_URL = os.getenv("RAG_QUERY_URL")


# async def call_rag_engine(query, chat_history, metadata):
#     payload = {
#         "query": query,
#         "chat_history": chat_history,
#         "metadata": metadata
#     }

#     async with httpx.AsyncClient() as client:
#         response = await client.post(
#             RAG_ENGINE_URL,
#             json=payload
#         )

#         response.raise_for_status()

#         return response.json()

async def call_rag_engine(query, chat_history, metadata):
    return {
        "answer": f"Dummy AI says: {query}",
        "sources": [
            {
                "doc": "Academic Rules",
                "page": 12
            }
        ]
    }