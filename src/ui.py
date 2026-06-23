from pydantic import BaseModel


def show_llm_response(response):
    print(f"\nAnswer: {response.answer}\n")
    print("Citations:")

    for count, citation in enumerate(response.citations):
        citation_text = [
            f"{key}: {value}" for key, value in citation.model_dump().items()
        ]
        print(f"{count + 1} {citation_text}")


def get_user_query():
    query = input("\nQuery: ")
    return query.strip()
