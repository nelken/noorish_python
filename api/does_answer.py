def does_answer(client, question: str, message: str) -> bool:
    """Return True if the message answers the question according to the model."""
    prompt = (
        f"Does the following message answer the question?\n" 
        f"Question: {question}\n"
        f"Message: {message}\n"
        "Respond with only 'true' or 'false'. If it only partially answers the question, reply with 'true'"
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}],
        max_tokens=5,
    )
    print (question)
    print(message)
    print(response)
    answer_text = response.choices[0].message.content.strip().lower()
    return answer_text == "true"
