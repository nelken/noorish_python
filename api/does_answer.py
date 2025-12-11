def too_short(client, question: str, answer: str) -> bool:
    
    prompt = (
        f"Consider the following question and answer pair: \n"
        f"Question: {question}\n"
        f"answer: {answer}\n"
        "would you consider this an answer of adequate length, or is it too short?\n"
        "for simple factual questions, such as 'what is your name', even a single word is sufficiently long\n"
        "for deeper questions, we want longer and more informative answers\n"
        #"explain your reasoning\n"
        "Respond with only 'too short' or 'long enough'. "
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}],
        max_tokens=2,
        temperature = 0.0
    )
    print(answer,"response", response)
    answer_text = response.choices[0].message.content.strip().lower()
    return answer_text == "too short"
    

def does_answer(client, question: str, message: str) -> bool:
    """Return True if the message answers the question according to the model."""
    prompt = (
        f"Does the following message answer the question?\n" 
        f"Question: {question}\n"
        f"Message: {message}\n"
        "Respond with only 'true' or 'false'. If it only partially answers the question, reply with 'true' "
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}],
        max_tokens=1,
        temperature = 0.0
    )
    answer_text = response.choices[0].message.content.strip().lower()
    return answer_text == "true"
