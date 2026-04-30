"""
trivia_system.py — Trivia Game Engine
=====================================
Manages trivia games with scoring, combos, streaks, and leaderboards.

Features:
  - 3 questions per game (exits if no response)
  - 7 seconds per question, 3 seconds to show answer
  - Time-based bonuses: <2s: +3, <3s: +2, <4s: +1
  - Combo system: 3 streak = +5 bonus, 5 streak = DOUBLE POINTS
  - Boss round (random, worth 30 points)
  - Leaderboard updates after each round
  - Only accepts correct answers once per player per round
"""

import asyncio
import random
import time
from datetime import datetime, timedelta

# Trivia question database
TRIVIA_QUESTIONS = [
    {"question": "What term describes awareness of one's own thoughts and existence?", "answer": "consciousness"},
    {"question": "In many spiritual traditions, what is the illusion of a separate 'self' called?", "answer": "ego"},
    {"question": "What universal principle states that like attracts like?", "answer": "attraction"},
    {"question": "What state of mind is often associated with deep meditation and presence?", "answer": "mindfulness"},
    {"question": "Unscramble: g w a n n a k i e", "answer": "awakening"},
    {"question": "Which universal law suggests everything is in constant motion?", "answer": "vibration"},
    {"question": "What is the term for hidden or secret knowledge?", "answer": "occult"},
    {"question": "In Hermetic philosophy, what principle means 'as above, so below'?", "answer": "correspondence"},
    {"question": "What mental faculty allows humans to create ideas beyond current reality?", "answer": "imagination"},
    {"question": "What is the practice of directing focused thought to influence outcomes often called?", "answer": "manifestation"},
    {"question": "What concept describes breaking free from limiting beliefs imposed by society?", "answer": "liberation"},
    {"question": "In many teachings, what is the opposite of fear in higher consciousness?", "answer": "love"},
    {"question": "What universal law states every action has a reaction?", "answer": "karma"},
    {"question": "What term is used for heightened inner knowing without reasoning?", "answer": "intuition"},
    {"question": "What is the idea that reality is shaped by perception called?", "answer": "subjectivity"},
    {"question": "In occult traditions, what is the unseen life-force often called?", "answer": "energy"},
    {"question": "Unscramble: t i p s o v y i t i", "answer": "positivity"},
    {"question": "What is the process of questioning reality and belief systems called?", "answer": "awakening"},
    {"question": "What universal law emphasizes balance between opposing forces?", "answer": "polarity"},
    {"question": "What inner quality is often said to free the mind from control and illusion?", "answer": "awareness"},
    {"question": "Which chakra is associated with the element 'ether' rather than a physical element?", "answer": "crown"},
    {"question": "In the tarot, which Major Arcana card is numbered 0?", "answer": "the fool"},
    {"question": "Which planet rules Scorpio in traditional astrology (not modern)?", "answer": "mars"},
    {"question": "What is the numerological reduction of 29?", "answer": "11"},
    {"question": "In Kabbalah, how many Sephirot are on the Tree of Life?", "answer": "10"},
    {"question": "Which chakra is located at the base of the spine?", "answer": "root"},
    {"question": "Which tarot card directly follows The Devil (XV)?", "answer": "the tower"},
    {"question": "Which zodiac sign is opposite Leo?", "answer": "aquarius"},
    {"question": "What number is associated with completion and endings in numerology?", "answer": "9"},
    {"question": "In Kabbalah, what is the topmost Sephirah called?", "answer": "keter"},
    {"question": "Which chakra is associated with the color green?", "answer": "heart"},
    {"question": "In tarot, which suit is associated with the element air?", "answer": "swords"},
    {"question": "Which planet rules Capricorn?", "answer": "saturn"},
    {"question": "What is the life path number of someone born on 10/10/2000?", "answer": "4"},
    {"question": "In Kabbalah, which Sephirah represents understanding?", "answer": "binah"},
    {"question": "Which chakra is linked to communication and truth?", "answer": "throat"},
    {"question": "Which tarot card is numbered XIII?", "answer": "death"},
    {"question": "Which zodiac sign is ruled by Venus and is an air sign?", "answer": "libra"},
    {"question": "What is the reduced numerology value of 777?", "answer": "3"},
    {"question": "In Kabbalah, what is the central Sephirah associated with balance and beauty?", "answer": "tipharet"},
    {"question": "Which Hebrew letter corresponds to The Fool in the Golden Dawn tarot system?", "answer": "aleph"},
    {"question": "What is the planetary correspondence of Tiferet on the Tree of Life?", "answer": "sun"},
    {"question": "Which chakra is associated with the bija mantra 'LAM'?", "answer": "root"},
    {"question": "In astrology, what is the exaltation sign of the Sun?", "answer": "aries"},
    {"question": "What is the numerological value of the Hebrew word 'Chai'?", "answer": "18"},
    {"question": "Which tarot card corresponds to the Hebrew letter Mem?", "answer": "the hanged man"},
    {"question": "What is the ruling planet of Aquarius in modern astrology?", "answer": "uranus"},
    {"question": "Which Sephirah is associated with Mercury?", "answer": "hod"},
    {"question": "What chakra is linked to the pineal gland?", "answer": "third eye"},
    {"question": "What is 44 reduced in numerology, keeping master numbers?", "answer": "44"},
    {"question": "Which zodiac sign is the detriment of the Moon?", "answer": "capricorn"},
    {"question": "What tarot card is associated with the zodiac sign Scorpio?", "answer": "death"},
    {"question": "Which Sephirah represents wisdom (not understanding)?", "answer": "chokmah"},
    {"question": "What is the element of the suit of Pentacles?", "answer": "earth"},
    {"question": "What is the vibrational root number of 1234?", "answer": "1"},
    {"question": "Which Hebrew letter corresponds to The Magician?", "answer": "beth"},
    {"question": "Which planet is in fall in Libra?", "answer": "sun"},
    {"question": "Which chakra governs personal power and will?", "answer": "solar plexus"},
    {"question": "Which Sephirah is directly below Keter on the Tree of Life (right pillar)?", "answer": "chokmah"},
    {"question": "What is the numerological reduction of 1919?", "answer": "2"},
]

BOSS_QUESTIONS = [
    {"question": "Which planet rules Scorpio? (traditional rulership only)", "answer": "mars"},
    {"question": "What is the number of The Fool in standard tarot numbering?", "answer": "0"},
    {"question": "What is the reduced numerology value of 11? (do NOT keep master numbers)", "answer": "2"},
    {"question": "Which element is associated with the suit of Swords?", "answer": "air"},
    {"question": "Which chakra is the fourth chakra from the base?", "answer": "heart"},
    {"question": "Which zodiac sign is ruled by Saturn? (name ONE)", "answer": "capricorn"},
    {"question": "What is the numerological reduction of 10?", "answer": "1"},
    {"question": "Which tarot card is XIII?", "answer": "death"},
    {"question": "Which Sephirah is associated with the Moon?", "answer": "yesod"},
    {"question": "What is the element of Earth signs?", "answer": "earth"},
    {"question": "Which chakra is associated with intuition (NOT communication)?", "answer": "third eye"},
    {"question": "Which planet is exalted in Aries?", "answer": "sun"},
    {"question": "What is the reduced value of 19 in numerology?", "answer": "1"},
    {"question": "Which tarot suit corresponds to the element Earth?", "answer": "pentacles"},
    {"question": "Which Sephirah represents the material world?", "answer": "malkuth"},
    {"question": "Which zodiac sign comes immediately after Pisces?", "answer": "aries"},
    {"question": "What is the numerological reduction of 1001?", "answer": "2"},
    {"question": "Which tarot card is numbered I?", "answer": "the magician"},
    {"question": "Which chakra is at the very top of the head?", "answer": "crown"},
    {"question": "Which Hebrew letter corresponds to The Magician?", "answer": "beth"},
]


class TriviaEngine:
    """Manages a trivia game session."""
    
    def __init__(self):
        self.running = False
        self.active = False
        self.force_stop = False
        
        self.current_question = None
        self.question_number = 0
        self.scores = {}  # {user_id: {"name": str, "pts": int, "xp": int, "streak": int}}
        self.correct_answers = set()  # Prevent multiple correct answers same question
        self.player_answers = {}  # {user_id: (answer, time_taken)}
        self.is_boss_round = False
        self.empty_rounds = 0
        self.question_start_time = 0
        
    def reset(self):
        """Reset game state between rounds."""
        self.scores = {}
        self.correct_answers = set()
        self.player_answers = {}
        self.current_question = None
        
    def pick_question(self) -> dict:
        """Pick a random trivia question (10% chance for boss)."""
        self.is_boss_round = random.random() < 0.10
        questions = BOSS_QUESTIONS if self.is_boss_round else TRIVIA_QUESTIONS
        return random.choice(questions)
    
    def normalize_answer(self, text: str) -> str:
        """Normalize user answer for comparison - handles variations."""
        # Remove extra whitespace and convert to lowercase
        text = text.strip().lower()
        
        # Remove common filler words
        text = text.replace(" chakra", "").replace(" the ", " ").strip()
        text = text.replace("the ", "").replace(" the", "")
        
        # Handle common abbreviations/variations
        text = text.replace("3rd ", "").replace("third ", "")
        text = text.replace("solar plexus", "solplexus")
        text = text.replace("heart chakra", "heart").replace("heart", "heart")
        text = text.replace("crown chakra", "crown")
        text = text.replace("root chakra", "root")
        text = text.replace("third eye", "thirdeye")
        text = text.replace("throat chakra", "throat")
        text = text.replace("sacral chakra", "sacral")
        
        return text
    
    def calculate_bonus(self, time_taken: float) -> int:
        """Calculate time bonus based on response time."""
        if time_taken < 2.0:
            return 3
        elif time_taken < 3.0:
            return 2
        elif time_taken < 4.0:
            return 1
        return 0
    
    def calculate_streak_bonus(self, streak: int, base_points: int) -> tuple[int, str]:
        """Calculate streak bonus multiplier and message."""
        bonus_msg = ""
        bonus_pts = 0
        
        if streak >= 5:
            # Double points
            bonus_pts = base_points
            bonus_msg = "🔥🔥 5-STREAK! DOUBLE POINTS!"
        elif streak >= 3:
            # +5 bonus
            bonus_pts = 5
            bonus_msg = "🔥 3-STREAK! +5 BONUS!"
        
        return bonus_pts, bonus_msg
    
    def add_score(self, user_id: str, username: str, points: int, xp: int, time_taken: float = 0):
        """Add score for a player."""
        if user_id not in self.scores:
            self.scores[user_id] = {
                "name": username,
                "pts": 0,
                "xp": 0,
                "streak": 0,
                "answers": 0
            }
        
        # Increment streak
        self.scores[user_id]["streak"] += 1
        self.scores[user_id]["answers"] += 1
        
        # Calculate time bonus
        time_bonus = self.calculate_bonus(time_taken)
        
        # Calculate streak bonus
        current_streak = self.scores[user_id]["streak"]
        streak_bonus, streak_msg = self.calculate_streak_bonus(current_streak, points)
        
        # Total points: base + time bonus + streak bonus
        total_pts = points + time_bonus + streak_bonus
        
        # Boss round doubles points
        if self.is_boss_round:
            total_pts = total_pts * 2
        
        self.scores[user_id]["pts"] += total_pts
        self.scores[user_id]["xp"] += xp
        
        return {
            "total_points": total_pts,
            "base_points": points,
            "time_bonus": time_bonus,
            "streak_bonus": streak_bonus,
            "streak_msg": streak_msg,
            "time_msg": f" +{time_bonus} time bonus" if time_bonus > 0 else "",
            "streak": current_streak
        }
    
    def reset_streak(self, user_id: str):
        """Reset player streak on wrong answer."""
        if user_id in self.scores:
            self.scores[user_id]["streak"] = 0


active_trivia_games: dict[int, TriviaEngine] = {}


def get_trivia_engine(chat_id: int) -> TriviaEngine:
    """Get or create trivia engine for a chat."""
    if chat_id not in active_trivia_games:
        active_trivia_games[chat_id] = TriviaEngine()
    return active_trivia_games[chat_id]


def load_trivia_questions(custom_file: str = None) -> list[dict]:
    """Load trivia questions from file if available."""
    if custom_file:
        try:
            import json
            with open(custom_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to load custom trivia questions: {e}")
    return TRIVIA_QUESTIONS
