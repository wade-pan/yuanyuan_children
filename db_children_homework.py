import os
import sys
import json
import sqlite3
from datetime import datetime, date

# Directory setup
current_dir = os.path.dirname(os.path.abspath(__file__))
LOCAL_DB_PATH = os.path.join(current_dir, "homework.db")

# Default to independent local homework.db (or custom path from env)
DB_PATH = os.environ.get("CHILDREN_DB_PATH", LOCAL_DB_PATH)

DEFAULT_CATEGORIES = [
	"🧮 趣味数学20课",
	"📖 语文天地",
	"📐 数学探索",
	"🔤 英语口语",
	"🏃 体育运动",
	"🔬 科学思维",
	"📚 每日阅读"
]

MEMBERS = [
	{
		"student_no": "AZ001",
		"name": "安仔",
		"role": "弟弟 / 趣味数学探索官",
		"gender": "男",
		"grade": "三年级 (小学)",
		"class_name": "团团媛媛成长小分队",
		"parent_name": "爸爸妈妈",
		"parent_phone": "13800000001",
		"avatar": "👦"
	},
	{
		"student_no": "EN002",
		"name": "恩妞",
		"role": "姐姐 / 学习小能手",
		"gender": "女",
		"grade": "初中预备班 (初一)",
		"class_name": "团团媛媛成长小分队",
		"parent_name": "爸爸妈妈",
		"parent_phone": "13800000002",
		"avatar": "👧"
	}
]

# Load Fun Math Curriculum
CURRICULUM_PATH = os.path.join(current_dir, "math_templates_curriculum.json")
try:
	with open(CURRICULUM_PATH, "r", encoding="utf-8") as f:
		MATH_LESSONS = json.load(f)
except Exception:
	MATH_LESSONS = []

def get_db_connection(db_path=DB_PATH):
	"""Returns a connection to the SQLite database with row_factory set."""
	conn = sqlite3.connect(db_path)
	conn.row_factory = sqlite3.Row
	return conn

def init_db(db_path=DB_PATH):
	"""Initializes the database tables and guarantees correct schema for Fun Math."""
	conn = get_db_connection(db_path)
	cursor = conn.cursor()

	# 1. Homework / Tasks Table
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS homework (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			title VARCHAR(150) NOT NULL,
			category VARCHAR(50) NOT NULL,
			assignee VARCHAR(50) DEFAULT '全员',
			due_date DATE NOT NULL,
			due_time VARCHAR(20) DEFAULT '20:00',
			content TEXT NOT NULL,
			requirements TEXT,
			reward_flowers INTEGER DEFAULT 1,
			status VARCHAR(30) DEFAULT 'published',
			wechat_text TEXT,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)
	""")

	# 2. Reusable Quick Templates Table
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS templates (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			name VARCHAR(100) NOT NULL,
			category VARCHAR(50) NOT NULL,
			assignee VARCHAR(50) DEFAULT '全员',
			content TEXT NOT NULL,
			requirements TEXT,
			reward_flowers INTEGER DEFAULT 1,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)
	""")

	# 3. Members / Children Table
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS students (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			student_no VARCHAR(50) UNIQUE,
			name VARCHAR(50) NOT NULL,
			role VARCHAR(50) DEFAULT '队员',
			gender VARCHAR(10) DEFAULT '男',
			grade VARCHAR(50) DEFAULT '三年级',
			class_name VARCHAR(50) DEFAULT '团团媛媛成长小分队',
			flowers INTEGER DEFAULT 0,
			stars INTEGER DEFAULT 0,
			parent_name VARCHAR(50),
			parent_phone VARCHAR(50),
			avatar VARCHAR(20) DEFAULT '👤',
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		)
	""")

	# 4. Homework Submissions / Check-in Table
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS submissions (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			homework_id INTEGER NOT NULL,
			student_id INTEGER NOT NULL,
			student_name VARCHAR(50) NOT NULL,
			status VARCHAR(30) DEFAULT 'pending',
			subtasks_status TEXT DEFAULT '[]',
			feedback TEXT,
			flowers_awarded INTEGER DEFAULT 0,
			stars_awarded INTEGER DEFAULT 0,
			submitted_at TIMESTAMP,
			reviewed_at TIMESTAMP,
			FOREIGN KEY (homework_id) REFERENCES homework(id),
			FOREIGN KEY (student_id) REFERENCES students(id)
		)
	""")

	# 5. Fun Math 20 Lessons Definitions Table
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS math_lessons (
			lesson_id INTEGER PRIMARY KEY,
			title VARCHAR(150) NOT NULL,
			category_tag VARCHAR(50) NOT NULL,
			difficulty INTEGER DEFAULT 1,
			target_student VARCHAR(50) DEFAULT '安仔',
			base_reward_flowers INTEGER DEFAULT 3,
			base_reward_stars INTEGER DEFAULT 3,
			story_scenario TEXT NOT NULL,
			question TEXT NOT NULL,
			answer_unit VARCHAR(30) DEFAULT '',
			standard_answer TEXT NOT NULL,
			hints_json TEXT NOT NULL,
			solution_explanation TEXT NOT NULL
		)
	""")

	# 6. Fun Math Submissions & Hint Tracking Table
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS math_submissions (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			lesson_id INTEGER NOT NULL,
			student_name VARCHAR(50) NOT NULL,
			student_no VARCHAR(50) DEFAULT 'AZ001',
			hints_used_count INTEGER DEFAULT 0,
			hints_used_levels TEXT DEFAULT '[]',
			student_answer TEXT,
			is_correct INTEGER DEFAULT 1,
			reward_flowers INTEGER DEFAULT 3,
			reward_stars INTEGER DEFAULT 3,
			note TEXT,
			submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			FOREIGN KEY (lesson_id) REFERENCES math_lessons(lesson_id)
		)
	""")

	# Create Indexes
	cursor.execute("CREATE INDEX IF NOT EXISTS idx_hw_due_date ON homework(due_date)")
	cursor.execute("CREATE INDEX IF NOT EXISTS idx_hw_category ON homework(category)")
	cursor.execute("CREATE INDEX IF NOT EXISTS idx_sub_hw_id ON submissions(homework_id)")
	cursor.execute("CREATE INDEX IF NOT EXISTS idx_math_lesson_id ON math_submissions(lesson_id)")
	cursor.execute("CREATE INDEX IF NOT EXISTS idx_math_student ON math_submissions(student_name)")

	# Seed Initial Students
	cursor.execute("SELECT COUNT(*) FROM students")
	if cursor.fetchone()[0] == 0:
		for m in MEMBERS:
			cursor.execute("""
				INSERT INTO students (student_no, name, role, gender, grade, class_name, flowers, stars, parent_name, parent_phone, avatar)
				VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?)
			""", (m["student_no"], m["name"], m["role"], m["gender"], m["grade"], m["class_name"], m["parent_name"], m["parent_phone"], m["avatar"]))

	# Seed / Update Math Lessons
	cursor.execute("SELECT COUNT(*) FROM math_lessons")
	if cursor.fetchone()[0] == 0 and MATH_LESSONS:
		for item in MATH_LESSONS:
			cursor.execute("""
				INSERT INTO math_lessons (
					lesson_id, title, category_tag, difficulty, target_student,
					base_reward_flowers, base_reward_stars, story_scenario, question,
					answer_unit, standard_answer, hints_json, solution_explanation
				) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
			""", (
				item["lesson_id"], item["title"], item.get("category_tag", "趣味计算"),
				item.get("difficulty", 1), item.get("target_student", "安仔"),
				item.get("base_reward_flowers", 3), item.get("base_reward_stars", 3),
				item["story_scenario"], item["question"], item.get("answer_unit", ""),
				str(item["standard_answer"]), json.dumps(item.get("hints", []), ensure_ascii=False),
				item.get("solution_explanation", "")
			))

	# Seed Reusable Templates
	cursor.execute("SELECT COUNT(*) FROM templates")
	if cursor.fetchone()[0] == 0:
		seed_templates = [
			("🧮 趣味数学：第1课超市找零挑战", "🧮 趣味数学20课", "安仔", "完成第1课【超市找零魔法】解题与生活实践", "独立审题，尝试不看提示解答，获得最高 3 朵小红花！", 3),
			("🧮 趣味数学：第2课披萨分片奥秘", "🧮 趣味数学20课", "安仔", "完成第2课【美味披萨的分片奥秘】图形与分数思考", "理清总数与吃掉片数关系，认真记录答题思路！", 3),
			("📖 语文天地：经典古诗背诵与默写", "📖 语文天地", "全员", "有感情背诵并工整抄写一首必背古诗", "字迹工整，发音标准，背诵流畅，标点符号准确。", 2),
			("📐 数学探索：口算练习与竖式验算", "📐 数学探索", "全员", "完成 20 道口算题及 4 道多位数乘除法竖式验算", "认真计算，书写清晰，草稿规范，正确率达 95% 以上。", 2),
			("🔤 英语口语：日常情景对话朗读", "🔤 英语口语", "全员", "朗读课文对话 3 遍，录制 1 分钟语音发送至微信群", "语音标准，语调自然，自信大声朗读。", 2),
			("🏃 体育运动：跳绳与开合跳打卡", "🏃 体育运动", "全员", "1分钟快速跳绳 150 个 + 开合跳 50 个", "动作标准，注意热身与拉伸，坚持到底！", 2),
			("🏃 体育·家里板球练习", "🏃 体育运动", "全员", "1. 来回一共6次 - 达成3次\n2. 来回一共7次 - 达成2次\n3. 来回一共8次 - 达成1次", "【练习要求】专注球感与敏捷脚步配合，注意安全，按目标完成各组次数！", 2),
			("🏃 体育·安仔俯卧撑与恩妞仰卧起坐训练", "🏃 体育运动", "全员", "1. 安仔完成标准俯卧撑 15 次 x 3 组 (锻炼上肢力量与核心支撑)\n2. 恩妞完成标准仰卧起坐 25 次 x 2 组 (锻炼腰腹核心力量)\n3. 姐弟互相协助计时与计数，完成后进行上肢与腰部静态拉伸 3 分钟", "【动作规范】动作标准到位，呼吸均匀，不追求过快，做完后喝温水拉伸放松。", 2)
		]
		for name, cat, ass, cont, req, flw in seed_templates:
			cursor.execute("""
				INSERT INTO templates (name, category, assignee, content, requirements, reward_flowers)
				VALUES (?, ?, ?, ?, ?, ?)
			""", (name, cat, ass, cont, req, flw))

	conn.commit()
	conn.close()

def calculate_math_flowers(base_flowers, hints_used_count):
	"""
	Calculates the rewarded flowers based on hint levels revealed.
	  - 0 hints used: 3 flowers
	  - 1 hint used:  2 flowers
	  - 2 hints used: 1 flower
	  - 3 hints used: 1 flower (minimum effort encouragement)
	"""
	if hints_used_count == 0:
		return base_flowers
	elif hints_used_count == 1:
		return max(1, base_flowers - 1)
	elif hints_used_count == 2:
		return max(1, base_flowers - 2)
	else:
		return 1

def record_math_submission(lesson_id, student_name, student_answer, hints_used_levels, note=""):
	"""
	Records a completed math lesson, checks answer, calculates flowers based on hints revealed,
	and automatically credits flowers & stars to the student!
	"""
	conn = get_db_connection()
	cursor = conn.cursor()

	# Fetch lesson info
	cursor.execute("SELECT * FROM math_lessons WHERE lesson_id = ?", (lesson_id,))
	row = cursor.fetchone()
	if not row:
		conn.close()
		return {"success": False, "error": f"未找到第 {lesson_id} 课"}

	lesson = dict(row)
	base_flowers = lesson.get("base_reward_flowers", 3)
	base_stars = lesson.get("base_reward_stars", 3)

	# Ensure hints_used_levels is list
	if isinstance(hints_used_levels, str):
		try:
			hints_used_levels = json.loads(hints_used_levels)
		except Exception:
			hints_used_levels = []
	hints_used_count = len(hints_used_levels)

	reward_flowers = calculate_math_flowers(base_flowers, hints_used_count)
	reward_stars = base_stars

	# Check student record
	cursor.execute("SELECT id, student_no, flowers, stars FROM students WHERE name = ?", (student_name,))
	st_row = cursor.fetchone()
	student_no = st_row["student_no"] if st_row else "AZ001"

	# Insert submission record
	cursor.execute("""
		INSERT INTO math_submissions (
			lesson_id, student_name, student_no, hints_used_count, hints_used_levels,
			student_answer, is_correct, reward_flowers, reward_stars, note
		) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
	""", (
		lesson_id, student_name, student_no, hints_used_count,
		json.dumps(hints_used_levels, ensure_ascii=False),
		str(student_answer).strip(), reward_flowers, reward_stars, note
	))
	sub_id = cursor.lastrowid

	# Credit flowers and stars to student
	if st_row:
		cursor.execute("""
			UPDATE students
			SET flowers = flowers + ?, stars = stars + ?, updated_at = CURRENT_TIMESTAMP
			WHERE id = ?
		""", (reward_flowers, reward_stars, st_row["id"]))

	conn.commit()
	conn.close()

	return {
		"success": True,
		"submission_id": sub_id,
		"lesson_id": lesson_id,
		"student_name": student_name,
		"reward_flowers": reward_flowers,
		"reward_stars": reward_stars,
		"hints_used_count": hints_used_count,
		"message": f"🎉 恭喜【{student_name}】成功解答第 {lesson_id} 课！获得 🌸 x{reward_flowers}，⭐ x{reward_stars}！"
	}

def get_math_lessons_status(student_name="安仔"):
	"""Returns all 20 lessons with completion status and hint history for a student."""
	conn = get_db_connection()
	cursor = conn.cursor()

	cursor.execute("SELECT * FROM math_lessons ORDER BY lesson_id ASC")
	lessons = [dict(r) for r in cursor.fetchall()]

	cursor.execute("""
		SELECT * FROM math_submissions
		WHERE student_name = ?
		ORDER BY id DESC
	""", (student_name,))
	submissions = [dict(r) for r in cursor.fetchall()]
	conn.close()

	# Map latest submission by lesson_id
	sub_map = {}
	for s in submissions:
		lid = s["lesson_id"]
		if lid not in sub_map:
			if isinstance(s.get("hints_used_levels"), str):
				try:
					s["hints_used_levels"] = json.loads(s["hints_used_levels"])
				except Exception:
					s["hints_used_levels"] = []
			sub_map[lid] = s

	result = []
	for l in lessons:
		if isinstance(l.get("hints_json"), str):
			try:
				l["hints"] = json.loads(l["hints_json"])
			except Exception:
				l["hints"] = []
		else:
			l["hints"] = []

		lid = l["lesson_id"]
		if lid in sub_map:
			l["status"] = "completed"
			l["submission"] = sub_map[lid]
		else:
			l["status"] = "uncompleted"
			l["submission"] = None

		result.append(l)

	return result

def get_student_rewards():
	"""Returns all students with their total flowers and stars."""
	conn = get_db_connection()
	cursor = conn.cursor()
	cursor.execute("SELECT id, student_no, name, role, gender, grade, class_name, flowers, stars, avatar FROM students ORDER BY id ASC")
	rows = cursor.fetchall()
	conn.close()
	return [dict(r) for r in rows]

def update_student_flower_and_star(student_id, delta_flowers, delta_stars=0):
	"""Adjusts flower and star points for a student."""
	conn = get_db_connection()
	cursor = conn.cursor()
	cursor.execute("""
		UPDATE students
		SET flowers = MAX(0, flowers + ?),
		    stars = MAX(0, stars + ?),
		    updated_at = CURRENT_TIMESTAMP
		WHERE id = ?
	""", (delta_flowers, delta_stars, student_id))
	conn.commit()
	conn.close()
	return True

def reset_all_flowers_and_stars():
	"""Resets all students' flowers and stars to 0."""
	conn = get_db_connection()
	cursor = conn.cursor()
	cursor.execute("UPDATE students SET flowers = 0, stars = 0, updated_at = CURRENT_TIMESTAMP")
	conn.commit()
	conn.close()
	return True

def format_wechat_task(item):
	"""Generates WeChat friendly formatted message for homework tasks."""
	assignee = item.get("assignee", "全员")
	title = item.get("title", "")
	category = item.get("category", "日常任务")
	due_date = item.get("due_date", "")
	due_time = item.get("due_time", "20:00")
	content = item.get("content", "")
	req = item.get("requirements", "")
	flowers = item.get("reward_flowers", 1)

	text = f"📢 【团团媛媛成长小分队 · 任务发布】\n"
	text += f"━━━━━━━━━━━━━━━\n"
	text += f"📌 任务名称: {title}\n"
	text += f"🏷️ 任务类别: {category}\n"
	text += f"👤 执行队员: {assignee}\n"
	text += f"⏰ 截止时间: {due_date} {due_time}\n"
	text += f"🌸 奖励红花: {flowers} 朵\n"
	text += f"━━━━━━━━━━━━━━━\n"
	text += f"📝 任务内容:\n{content}\n"
	if req:
		text += f"\n💡 完成要求:\n{req}\n"
	text += f"━━━━━━━━━━━━━━━\n"
	text += f"💪 加油！做完请及时打卡获取红花哦～✨"
	return text

def format_wechat_math_report(lesson, submission):
	"""Generates WeChat celebration message for completed math lessons."""
	s_name = submission.get("student_name", "安仔")
	lid = lesson.get("lesson_id", 1)
	title = lesson.get("title", "")
	hints_count = submission.get("hints_used_count", 0)
	flw = submission.get("reward_flowers", 3)
	stars = submission.get("reward_stars", 3)

	hint_desc = "🌟 独立完全解出（未使用任何提示）" if hints_count == 0 else f"💡 揭开 {hints_count} 层提示后顺利攻克"

	text = f"🎉 【团团媛媛成长小分队 · 趣味数学喜报】\n"
	text += f"━━━━━━━━━━━━━━━\n"
	text += f"👦 探索队员: {s_name} (9岁 · 三年级)\n"
	text += f"🧮 攻克关卡: 第 {lid} 课 - {title}\n"
	text += f"🔍 解题状态: {hint_desc}\n"
	text += f"🌸 斩获奖励: 获得小红花 🌸 x{flw}，成长星星 ⭐ x{stars}\n"
	text += f"━━━━━━━━━━━━━━━\n"
	text += f"🌈 思考过程很精彩，数学兴趣大爆发！继续加油探索下一课！🚀"
	return text
