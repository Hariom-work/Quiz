from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from motor.motor_asyncio import AsyncIOMotorClient
import json
from typing import Dict, List

app = FastAPI()

# MongoDB connection
MONGO_URI = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGO_URI)
db = client["quiz_db"]
quiz_collection = db["quizzes"]
submission_collection = db["submissions"]

# Sample quiz data
QUIZ_DATA = {
    "quiz1": {
        "questions": [
            {"id": "q1", "question": "What is 2+2?", "options": ["A: 3", "B: 4", "C: 5", "D: 6"], "answer": "B"},
            {"id": "q2", "question": "Capital of India?", "options": ["A: Delhi", "B: Mumbai", "C: Hyderabad", "D: Agra"], "answer": "A"},
            {"id": "q3", "question": "5 x 3 = ?", "options": ["A: 10", "B: 15", "C: 20", "D: 25"], "answer": "B"},
            {"id": "q4", "question": "Capital of M.P?", "options": ["A: Jabalpur", "B: Indore", "C: Bhopal", "D: Betul"], "answer": "C"},
            {"id": "q5", "question": "Pandas is written in?", "options": ["A: C", "B: C++", "C: Python", "D: Java"], "answer": "B"},
        ]
    }
}

# Store quiz data in MongoDB at startup
@app.on_event("startup")
async def load_quiz_data():
    for quiz_id, quiz in QUIZ_DATA.items():
        existing_quiz = await quiz_collection.find_one({"quiz_id": quiz_id})
        if not existing_quiz:
            await quiz_collection.insert_one({"quiz_id": quiz_id, "questions": quiz["questions"]})

async def evaluate_quiz(quiz_id: str, answers: Dict[str, str]):
    quiz = await quiz_collection.find_one({"quiz_id": quiz_id})
    if not quiz:
        return {"error": "Quiz not found"}

    total_questions = len(quiz["questions"])
    correct_count = sum(1 for q in quiz["questions"] if answers.get(q["id"]) == q["answer"])

    score_percentage = (correct_count / total_questions) * 100 if total_questions > 0 else 0
    feedback = generate_feedback(score_percentage)

    result = {
        "total_questions": total_questions,
        "correct": correct_count,
        "incorrect": total_questions - correct_count,
        "score_percentage": score_percentage,
        "feedback": feedback,
    }

    return result

def generate_feedback(score):
    if score >= 90:
        return "Excellent performance! Keep it up!"
    elif score >= 60:
        return "Good job! Revise the missed topics."
    else:
        return "Needs improvement. Consider reviewing key concepts."

@app.websocket("/ws/quiz")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            quiz_submission = json.loads(data)
            quiz_id = quiz_submission.get("quiz_id")
            student_id = quiz_submission.get("student_id")
            answers = quiz_submission.get("answers", {})

            result = await evaluate_quiz(quiz_id, answers)
            response = {"student_id": student_id, **result}

            # Store student submission in MongoDB
            await submission_collection.insert_one({"student_id": student_id, "quiz_id": quiz_id, "answers": answers, **result})

            await websocket.send_text(json.dumps(response))
    except WebSocketDisconnect:
        print("Client disconnected")
