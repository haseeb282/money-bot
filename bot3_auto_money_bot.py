import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

API_TOKEN = 'YOUR_BOT_TOKEN'
ADMIN_ID = 123456789  # Replace with your Telegram ID
bot = telebot.TeleBot(API_TOKEN)

conn = sqlite3.connect('bot3_data.db', check_same_thread=False)
cursor = conn.cursor()

# Setup database
cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL, referred_by INTEGER)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, url TEXT, reward REAL)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS completions (user_id INTEGER, task_id INTEGER, timestamp DATETIME)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS analytics (user_id INTEGER, action TEXT, timestamp DATETIME)''')
conn.commit()

scheduler = BackgroundScheduler()
scheduler.start()

def add_user(user_id, referred_by=None):
    cursor.execute("INSERT OR IGNORE INTO users (user_id, balance, referred_by) VALUES (?, ?, ?)", (user_id, 0.0, referred_by))
    conn.commit()

def log_action(user_id, action):
    cursor.execute("INSERT INTO analytics (user_id, action, timestamp) VALUES (?, ?, ?)",
                   (user_id, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def get_all_users():
    cursor.execute("SELECT user_id FROM users")
    return [user[0] for user in cursor.fetchall()]

def update_balance(user_id, amount):
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def get_balance(user_id):
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()[0]

def send_daily_tasks():
    cursor.execute("SELECT * FROM tasks")
    tasks = cursor.fetchall()
    for user_id in get_all_users():
        for task in tasks:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("Do Task", url=task[2]))
            bot.send_message(user_id, f"💼 Task: {task[1]}\n💵 Reward: ${task[3]}", reply_markup=markup)

scheduler.add_job(send_daily_tasks, 'interval', hours=24, start_date="2025-04-09 09:00:00")

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    args = message.text.split()
    referred_by = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    add_user(user_id, referred_by)
    log_action(user_id, "started bot")
    bot.reply_to(message, "Welcome to Auto Earning Bot! Use /tasks to start earning.")

@bot.message_handler(commands=['tasks'])
def show_tasks(message):
    cursor.execute("SELECT * FROM tasks")
    tasks = cursor.fetchall()
    if not tasks:
        return bot.reply_to(message, "No tasks available right now.")
    
    for task in tasks:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Do Task", url=task[2]))
        bot.send_message(message.chat.id, f"🧾 Task: {task[1]}\n💰 Reward: ${task[3]}", reply_markup=markup)

@bot.message_handler(commands=['done'])
def complete_task(message):
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return bot.reply_to(message, "Usage: /done <task_id>")

    task_id = int(parts[1])
    user_id = message.chat.id
    cursor.execute("SELECT * FROM completions WHERE user_id=? AND task_id=?", (user_id, task_id))
    if cursor.fetchone():
        return bot.reply_to(message, "You already completed this task!")

    cursor.execute("SELECT reward FROM tasks WHERE id=?", (task_id,))
    result = cursor.fetchone()
    if not result:
        return bot.reply_to(message, "Invalid task ID.")

    reward = result[0]
    update_balance(user_id, reward)
    cursor.execute("INSERT INTO completions (user_id, task_id, timestamp) VALUES (?, ?, ?)", (user_id, task_id, datetime.now()))
    conn.commit()
    bot.reply_to(message, f"✅ Task Completed! You earned ${reward:.2f}")

@bot.message_handler(commands=['balance'])
def balance(message):
    user_id = message.chat.id
    bal = get_balance(user_id)
    bot.reply_to(message, f"💸 Your current balance is ${bal:.2f}")

@bot.message_handler(commands=['addtask'])
def add_task(message):
    if message.chat.id != ADMIN_ID:
        return bot.reply_to(message, "Not authorized.")
    
    try:
        _, title, url, reward = message.text.split('|')
        cursor.execute("INSERT INTO tasks (title, url, reward) VALUES (?, ?, ?)", (title.strip(), url.strip(), float(reward.strip())))
        conn.commit()
        bot.reply_to(message, "✅ Task added successfully!")
    except:
        bot.reply_to(message, "Usage: /addtask |Title|URL|Reward")

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.chat.id != ADMIN_ID:
        return bot.reply_to(message, "Not authorized.")
    
    msg = message.text.replace("/broadcast", "").strip()
    for uid in get_all_users():
        try:
            bot.send_message(uid, msg)
        except:
            pass
    bot.reply_to(message, "Broadcast sent.")

@bot.message_handler(commands=['analytics'])
def analytics(message):
    if message.chat.id != ADMIN_ID:
        return bot.reply_to(message, "Not authorized.")
    
    cursor.execute("SELECT user_id, action, timestamp FROM analytics ORDER BY timestamp DESC LIMIT 20")
    logs = cursor.fetchall()
    text = "📊 Last 20 Actions:\n"
    for log in logs:
        text += f"👤 {log[0]} - {log[1]} at {log[2]}\n"
    bot.reply_to(message, text)

bot.polling()
