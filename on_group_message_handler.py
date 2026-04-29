"""
Clean on_group_message handler for main.py
This file contains a working version of the word validation handler.
Copy the function below into main.py to replace the corrupted version.
"""

# ═══════════════════════════════════════════════════════════════════════════
#  WORD-GUESS CATCH-ALL  ←── MUST BE THE LAST @dp.message HANDLER
# ═══════════════════════════════════════════════════════════════════════════

@dp.message(F.chat.type.in_({"group","supergroup"}))
async def on_group_message(message: types.Message):
    """Catch-all handler for word guesses during active fusion rounds."""
    try:
        if not message.text: 
            return
        
        text = message.text.strip()
        u_id = str(message.from_user.id)
        print(f"[MSG] '{text}' from {u_id}")

        # Commands not matched above — skip silently
        if text.startswith("!") or text.startswith("/"): 
            print(f"[SKIP] Command detected")
            return

        # Get game engine and user
        eng = get_engine(message.chat.id)
        user = get_user(u_id)
        print(f"[USER] {user.get('username') if user else 'NOT_REGISTERED'}, eng.active={eng.active}")

        # Must be registered
        if not user:
            if random.random() < 0.25:
                await message.reply(_unreg(), parse_mode="Markdown")
            print(f"[SKIP] User not registered")
            return

        # Check if round is active
        if not eng.active:
            print(f"[SKIP] Round not active")
            return

        # Prevent spam
        if eng.msg_count >= 4:
            eng.msg_count = 0
            await message.answer(f"📌 *Still playing:* `{eng.word1}` + `{eng.word2}`", parse_mode="Markdown")
            return

        # Validate word format
        guess = text.lower().strip()
        if len(guess) < 3: 
            print(f"[SKIP] Too short: {len(guess)} chars")
            return
        
        # Check if already used
        if guess in eng.used_words:
            print(f"[SKIP] Already used this round")
            update_streak_and_award_food(u_id, correct=False, username=user.get("username", ""))
            await message.reply(f"❌ `{guess.upper()}` was already guessed!", parse_mode="Markdown")
            return
        
        # Check if can spell from letters
        if not can_spell(guess, eng.letters):
            print(f"[SKIP] Can't spell from available letters")
            await message.reply(f"❌ Can't spell `{guess.upper()}` from: `{eng.letters.upper()}`", parse_mode="Markdown")
            return

        # After valid word found:
        username = user.get("username", message.from_user.first_name)
        jammer_info = await handle_jammer_word_submission(
            bot, message, guess, u_id, username
        )

        if jammer_info["deleted"]:
            # Message was deleted, don't send group reply
            return

        # ════════════════════════════════════════════════════════════════════
        # WORD VALIDATION
        # ════════════════════════════════════════════════════════════════════
        
        # Ensure dictionary is loaded
        if len(DICTIONARY) == 0:
            print(f"[WARN] DICTIONARY empty, reloading...")
            load_dictionary()
            print(f"[WARN] Reloaded: {len(DICTIONARY)} words")
        
        is_valid = word_in_dict(guess)
        print(f"[CHECK] '{guess}' valid={is_valid} (dict size: {len(DICTIONARY)})")
        
        if not is_valid:
            print(f"[INVALID] '{guess}' not in dictionary")
            update_streak_and_award_food(u_id, correct=False, username=user.get("username", ""))
            await message.reply(f"❌ `{guess.upper()}` is not a valid word.", parse_mode="Markdown")
            return

        # ════════════════════════════════════════════════════════════════════
        # VALID WORD - Award points and process
        # ════════════════════════════════════════════════════════════════════
        
        print(f"[VALID] `{guess}` found in dictionary - processing...")
        
        eng.used_words.append(guess)
        eng.msg_count += 1
        
        # Calculate base points
        pts = max(len(guess) - 2, 1)
        db_name = user.get("username", message.from_user.first_name)
        word_len = len(guess)
        
        # Addictive Mechanics
        login_result = handle_daily_login(u_id)
        if login_result["success"]:
            daily_bonus = login_result["bonus"]
            pts += daily_bonus // 5
            print(f"[STREAK] {db_name}: Day {login_result['streak']}, +{login_result['bonus']} bonus")
        
        combo = increment_combo(u_id)
        combo_mult = combo["multiplier"]
        pts = int(pts * combo_mult)
        
        # Resources
        resources_awarded = {}
        if word_len == 4:
            resources_awarded = {'wood': 1}
        elif word_len == 5:
            resources_awarded = {'bronze': 1}
        elif word_len == 6:
            resources_awarded = {'iron': 1}
        elif word_len == 7:
            resources_awarded = {'diamond': 1}
        elif word_len >= 8:
            resources_awarded = {'relics': 1}
        
        # Streak/food
        streak_info = update_streak_and_award_food(u_id, correct=True, username=db_name)
        
        # Rare items
        rare_item = check_rare_drop()
        rare_message = ""
        if rare_item:
            add_unclaimed_item(u_id, rare_item["key"], 1)
            rare_message = f"\n\n🎉 {format_rare_drop_notification(rare_item)}"
        
        # Build feedback message
        fb = f"✅ `{guess.upper()}` +{pts} pts  ⭐ +{pts} XP"
        
        if combo_mult > 1.0:
            fb += f" 🔥x{combo_mult}"
        
        # Add resources
        for resource, amount in resources_awarded.items():
            emoji_map = {"wood": "🪵", "bronze": "🧱", "iron": "⛓️", "diamond": "💎", "relics": "🏺"}
            emoji = emoji_map.get(resource, "📦")
            fb += f" +{amount} {emoji}"
        
        # Add food
        if streak_info.get("food_awarded", 0) > 0:
            fb += f" +{streak_info['food_awarded']} 🌽"
        
        # Add combo milestone
        if combo.get("milestone_message"):
            fb += f"\n\n{combo['milestone_message']}"
        
        # Add rare drop
        fb += rare_message
        
        # Send feedback
        await message.reply(fb, parse_mode="Markdown")
        print(f"[SENT] Feedback to {db_name}")
        
        # Save to database (background)
        try:
            user_fresh = get_user(u_id)
            if user_fresh:
                # Initialize base_resources if needed
                if 'base_resources' not in user_fresh:
                    user_fresh['base_resources'] = {'resources': {}, 'food': 0, 'current_streak': 0}
                
                base_res = user_fresh['base_resources']
                if 'resources' not in base_res:
                    base_res['resources'] = {}
                
                # Add resources
                res_dict = base_res['resources']
                for res_type, amount in resources_awarded.items():
                    res_dict[res_type] = res_dict.get(res_type, 0) + amount
                
                # Save
                user_fresh['base_resources'] = base_res
                save_user(u_id, user_fresh)
                add_points(u_id, pts, db_name)
                add_xp(u_id, pts)
                print(f"[DB] Saved for {db_name}")
        except Exception as e:
            print(f"[DB ERROR] {e}")
        
        # Update scores
        if u_id not in eng.scores:
            eng.scores[u_id] = {"pts": 0, "name": db_name, "user_id": u_id}
        eng.scores[u_id]["pts"] += pts
    
    except Exception as e:
        print(f"[HANDLER ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        try:
            await message.reply("⚠️ Error processing word. Try again.", parse_mode="Markdown")
        except:
            pass


