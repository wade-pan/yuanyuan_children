import os
import sys
import json
import socket
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, make_response, session

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
	sys.path.insert(0, current_dir)

def get_all_local_ips():
	"""Discovers active local IPv4 addresses safely and quickly without blocking DNS resolution."""
	ips = set()
	probe_targets = ['8.8.8.8', '192.168.31.1', '192.168.0.1', '1.1.1.1']
	for target in probe_targets:
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			s.settimeout(0.05)
			s.connect((target, 80))
			ip = s.getsockname()[0]
			if ip and not ip.startswith('127.'):
				ips.add(ip)
			s.close()
		except Exception:
			pass
	return sorted(list(ips))

from db_children_homework import (
	init_db, get_db_connection, format_wechat_task, format_wechat_math_report,
	reset_all_flowers_and_stars, record_math_submission, get_math_lessons_status,
	get_student_rewards, update_student_flower_and_star,
	DEFAULT_CATEGORIES, MATH_LESSONS, DB_PATH
)

# Load configuration
CONFIG_PATH = os.path.join(current_dir, "config.json")
try:
	with open(CONFIG_PATH, "r", encoding="utf-8") as f:
		config_data = json.load(f)
except Exception:
	config_data = {
		"app_name": "TuanTuanYuanYuanTaskForce",
		"app_title": "安仔 恩妞任务小分队系统",
		"host": "0.0.0.0",
		"port": 5089,
		"default_grade": "三年级 & 初中预备班",
		"default_class": "团团媛媛成长小分队",
		"categories": DEFAULT_CATEGORIES
	}

# Initialize Flask App
app = Flask(__name__, template_folder=os.path.join(current_dir, "templates"))
app.secret_key = "tuantuan_yuanyuan_task_force_secret_key_2026"
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

# Initialize SQLite database on startup
init_db(DB_PATH)

@app.route("/")
def index():
	"""Renders the main children task force dashboard."""
	current_u = session.get("user")
	user_profile = None
	if current_u and "users" in config_data and current_u in config_data["users"]:
		u_info = dict(config_data["users"][current_u])
		u_info.pop("password", None)
		u_info["username"] = current_u
		user_profile = u_info

	response = make_response(render_template(
		"index.html",
		cfg=config_data,
		app_config=config_data,
		config=config_data,
		current_user=user_profile,
		today=date.today().strftime("%Y-%m-%d"),
		math_lessons=MATH_LESSONS,
		default_categories=DEFAULT_CATEGORIES
	))
	response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
	response.headers['Pragma'] = 'no-cache'
	response.headers['Expires'] = '0'
	return response

# ==========================================
# 0. User Authentication & Permissions APIs
# ==========================================

@app.route("/api/login", methods=["POST"])
def login_api():
	"""
	Authenticates user:
	  - anzai / anzai123 (安仔 · 弟弟 · 9岁 · 三年级)
	  - enniu / enniu123 (恩妞 · 姐姐 · 12岁 · 初中预备班)
	  - admin / admin1234 (家长管理员)
	"""
	try:
		data = request.json or {}
		username = str(data.get("username", "")).strip().lower()
		password = str(data.get("password", "")).strip()

		users_map = config_data.get("users", {})
		if username not in users_map:
			return jsonify({"success": False, "error": "用户名不存在，请检查后重试"})

		user_record = users_map[username]
		if user_record.get("password") != password:
			return jsonify({"success": False, "error": "密码错误，请重新输入"})

		session["user"] = username
		session["role"] = user_record.get("role", "child")

		user_profile = dict(user_record)
		user_profile.pop("password", None)
		user_profile["username"] = username

		return jsonify({
			"success": True,
			"user": user_profile,
			"message": f"欢迎回来，{user_profile.get('name')}！"
		})
	except Exception as e:
		return jsonify({"success": False, "error": str(e)})

@app.route("/api/current_user", methods=["GET"])
def get_current_user_api():
	"""Returns the currently logged-in user session."""
	username = session.get("user")
	users_map = config_data.get("users", {})
	if username and username in users_map:
		u_info = dict(users_map[username])
		u_info.pop("password", None)
		u_info["username"] = username
		return jsonify({"success": True, "logged_in": True, "user": u_info})
	return jsonify({"success": True, "logged_in": False, "user": None})

@app.route("/api/logout", methods=["POST"])
def logout_api():
	"""Logs out the current user session."""
	session.clear()
	return jsonify({"success": True, "message": "已安全退出登录"})

# ==========================================
# 1. 趣味数学 20 课 (Fun Math 20 Lessons) APIs
# ==========================================

@app.route("/api/math/lessons", methods=["GET"])
def get_math_lessons_api():
	"""Returns all 20 math lessons with progress for a specific student."""
	student_name = request.args.get("student_name", "安仔")
	try:
		lessons = get_math_lessons_status(student_name)
		return jsonify({"success": True, "lessons": lessons, "student_name": student_name})
	except Exception as e:
		return jsonify({"success": False, "error": str(e)})

@app.route("/api/math/lessons/<int:lesson_id>", methods=["GET"])
def get_single_math_lesson_api(lesson_id):
	"""Returns single math lesson details."""
	student_name = request.args.get("student_name", "安仔")
	try:
		lessons = get_math_lessons_status(student_name)
		for l in lessons:
			if l["lesson_id"] == lesson_id:
				return jsonify({"success": True, "lesson": l})
		return jsonify({"success": False, "error": f"未找到第 {lesson_id} 课"})
	except Exception as e:
		return jsonify({"success": False, "error": str(e)})

@app.route("/api/math/lessons/<int:lesson_id>/submit", methods=["POST"])
def submit_math_lesson_api(lesson_id):
	"""
	Submits answer for a math lesson, handles hint count, awards flowers & stars,
	and produces WeChat celebratory report text.
	"""
	try:
		data = request.json or {}
		student_name = data.get("student_name", "安仔")
		student_answer = str(data.get("student_answer", "")).strip()
		hints_used = data.get("hints_used_levels", [])
		note = data.get("note", "")

		res = record_math_submission(
			lesson_id=lesson_id,
			student_name=student_name,
			student_answer=student_answer,
			hints_used_levels=hints_used,
			note=note
		)

		if not res.get("success"):
			return jsonify(res)

		# Fetch lesson info to format WeChat broadcast text
		conn = get_db_connection()
		cursor = conn.cursor()
		cursor.execute("SELECT * FROM math_lessons WHERE lesson_id = ?", (lesson_id,))
		l_row = cursor.fetchone()
		conn.close()

		lesson_info = dict(l_row) if l_row else {}
		wechat_text = format_wechat_math_report(lesson_info, res)
		res["wechat_text"] = wechat_text

		return jsonify(res)
	except Exception as e:
		return jsonify({"success": False, "error": str(e)})

@app.route("/api/math/lessons/<int:lesson_id>/reset", methods=["POST"])
def reset_math_lesson_api(lesson_id):
	"""Resets a lesson submission so the student can retry."""
	try:
		data = request.json or {}
		student_name = data.get("student_name", "安仔")
		conn = get_db_connection()
		cursor = conn.cursor()
		cursor.execute("DELETE FROM math_submissions WHERE lesson_id = ? AND student_name = ?", (lesson_id, student_name))
		conn.commit()
		conn.close()
		return jsonify({"success": True, "message": f"第 {lesson_id} 课记录已重置，可以重新挑战！"})
	except Exception as e:
		return jsonify({"success": False, "error": str(e)})

# ==========================================
# 2. Homework & Tasks Management APIs
# ==========================================

@app.route("/api/homework", methods=["GET"])
def get_homework_list():
	"""Retrieves homework tasks list with submissions."""
	try:
		conn = get_db_connection()
		cursor = conn.cursor()
		cursor.execute("SELECT * FROM homework ORDER BY due_date DESC, id DESC")
		homework_rows = cursor.fetchall()

		result = []
		for hw in homework_rows:
			hw_dict = dict(hw)
			cursor.execute("SELECT * FROM submissions WHERE homework_id = ?", (hw_dict["id"],))
			sub_rows = cursor.fetchall()
			hw_dict["submissions"] = [dict(s) for s in sub_rows]
			result.append(hw_dict)

		conn.close()
		return jsonify({"success": True, "homework": result})
	except Exception as e:
		return jsonify({"success": False, "error": str(e)})

@app.route("/api/homework", methods=["POST"])
def create_homework():
	"""Creates a new homework task and auto-generates WeChat broadcast text."""
	try:
		data = request.json or {}
		title = data.get("title", "").strip()
		category = data.get("category", "日常任务").strip()
		assignee = data.get("assignee", "全员").strip()
		due_date = data.get("due_date", date.today().strftime("%Y-%m-%d"))
		due_time = data.get("due_time", "20:00")
		content = data.get("content", "").strip()
		requirements = data.get("requirements", "").strip()
		reward_flowers = int(data.get("reward_flowers", 1))

		if not title or not content:
			return jsonify({"success": False, "error": "任务标题和内容不能为空"})

		wechat_text = format_wechat_task({
			"title": title, "category": category, "assignee": assignee,
			"due_date": due_date, "due_time": due_time, "content": content,
			"requirements": requirements, "reward_flowers": reward_flowers
		})

		conn = get_db_connection()
		cursor = conn.cursor()
		cursor.execute("""
			INSERT INTO homework (title, category, assignee, due_date, due_time, content, requirements, reward_flowers, wechat_text)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
		""", (title, category, assignee, due_date, due_time, content, requirements, reward_flowers, wechat_text))
		hw_id = cursor.lastrowid

		# Create submission records for assignees
		cursor.execute("SELECT id, name FROM students")
		students = cursor.fetchall()
		for st in students:
			if assignee == "全员" or assignee == st["name"]:
				cursor.execute("""
					INSERT INTO submissions (homework_id, student_id, student_name, status)
					VALUES (?, ?, ?, 'pending')
				""", (hw_id, st["id"], st["name"]))

		conn.commit()
		conn.close()

		return jsonify({
			"success": True,
			"homework_id": hw_id,
			"wechat_text": wechat_text,
			"message": "🎉 任务发布成功！"
		})
	except Exception as e:
		return jsonify({"success": False, "error": str(e)})

@app.route("/api/homework/<int:hw_id>", methods=["DELETE"])
def delete_homework(hw_id):
	"""Deletes a homework task and its associated submissions."""
	try:
		conn = get_db_connection()
		cursor = conn.cursor()
		cursor.execute("DELETE FROM submissions WHERE homework_id = ?", (hw_id,))
		cursor.execute("DELETE FROM homework WHERE id = ?", (hw_id,))
		conn.commit()
		conn.close()
		return jsonify({"success": True, "message": "🗑️ 任务已成功删除"})
	except Exception as e:
		return jsonify({"success": False, "error": str(e)})

@app.route("/api/homework/<int:hw_id>/checkin", methods=["POST"])
def checkin_homework(hw_id):
	"""Marks homework completed by a student and rewards flowers."""
	try:
		data = request.json or {}
		student_name = data.get("student_name", "").strip()
		feedback = data.get("feedback", "").strip()

		conn = get_db_connection()
		cursor = conn.cursor()
		cursor.execute("SELECT reward_flowers FROM homework WHERE id = ?", (hw_id,))
		hw_row = cursor.fetchone()
		flowers = hw_row["reward_flowers"] if hw_row else 1

		cursor.execute("""
			UPDATE submissions
			SET status = 'completed', feedback = ?, flowers_awarded = ?, submitted_at = CURRENT_TIMESTAMP
			WHERE homework_id = ? AND student_name = ?
		""", (feedback, flowers, hw_id, student_name))

		cursor.execute("""
			UPDATE students
			SET flowers = flowers + ?, updated_at = CURRENT_TIMESTAMP
			WHERE name = ?
		""", (flowers, student_name))

		conn.commit()
		conn.close()
		return jsonify({"success": True, "message": f"🎉 恭喜【{student_name}】打卡成功！获得 🌸 x{flowers}"})
	except Exception as e:
		return jsonify({"success": False, "error": str(e)})

# ==========================================
# 3. Students & Flower Rewards APIs
# ==========================================

@app.route("/api/students", methods=["GET"])
def get_students_api():
	"""Returns all students and their flowers/stars."""
	try:
		students = get_student_rewards()
		return jsonify({"success": True, "students": students})
	except Exception as e:
		return jsonify({"success": False, "error": str(e)})

@app.route("/api/students/<int:student_id>/adjust", methods=["POST"])
def adjust_student_rewards(student_id):
	"""Adjusts student flowers and stars."""
	try:
		data = request.json or {}
		delta_flowers = int(data.get("delta_flowers", 0))
		delta_stars = int(data.get("delta_stars", 0))
		update_student_flower_and_star(student_id, delta_flowers, delta_stars)
		return jsonify({"success": True, "message": "🌸 积分更新成功！"})
	except Exception as e:
		return jsonify({"success": False, "error": str(e)})

@app.route("/api/students/reset_all", methods=["POST"])
def reset_all_rewards_api():
	"""Resets all students' flowers and stars."""
	try:
		reset_all_flowers_and_stars()
		return jsonify({"success": True, "message": "🔄 已清空所有队员的小红花与星星积分"})
	except Exception as e:
		return jsonify({"success": False, "error": str(e)})

def auto_git_sync_templates():
	"""
	Automatically commits and pushes template and curriculum changes to Git.
	"""
	try:
		import subprocess
		ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		git_env = os.environ.copy()
		git_env["GIT_AUTHOR_NAME"] = "wade-pan"
		git_env["GIT_AUTHOR_EMAIL"] = "wade-pan@users.noreply.github.com"
		git_env["GIT_COMMITTER_NAME"] = "wade-pan"
		git_env["GIT_COMMITTER_EMAIL"] = "wade-pan@users.noreply.github.com"
		
		cmd = f'git -C "{current_dir}" -c user.name="wade-pan" -c user.email="wade-pan@users.noreply.github.com" add math_templates_curriculum.json config.json templates/index.html && git -C "{current_dir}" -c user.name="wade-pan" -c user.email="wade-pan@users.noreply.github.com" commit -m "auto: sync template changes to git [{ts_str}]" && git -C "{current_dir}" push origin main'
		subprocess.Popen(cmd, shell=True, env=git_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	except Exception:
		pass

def check_is_admin():
	"""Checks whether the currently active session belongs to an admin."""
	return session.get("role") == "admin"

@app.route("/api/git/push", methods=["POST"])
def git_push_api():
	"""
	Executes Git Commit and Push to remote repository (Admin only).
	"""
	if not check_is_admin():
		return jsonify({"success": False, "error": "🔒 权限不足：只有家长管理员 (Admin) 可以执行 Git Push！"}), 403

	try:
		import subprocess
		git_env = os.environ.copy()
		git_env["GIT_AUTHOR_NAME"] = "wade-pan"
		git_env["GIT_AUTHOR_EMAIL"] = "wade-pan@users.noreply.github.com"
		git_env["GIT_COMMITTER_NAME"] = "wade-pan"
		git_env["GIT_COMMITTER_EMAIL"] = "wade-pan@users.noreply.github.com"

		ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		cmd = f'git -C "{current_dir}" -c user.name="wade-pan" -c user.email="wade-pan@users.noreply.github.com" add math_templates_curriculum.json config.json templates/index.html && git -C "{current_dir}" -c user.name="wade-pan" -c user.email="wade-pan@users.noreply.github.com" commit -m "update: sync custom templates by admin [{ts_str}]" && git -C "{current_dir}" push origin main'
		
		proc = subprocess.run(cmd, shell=True, env=git_env, text=True, capture_output=True, timeout=25)
		
		if proc.returncode != 0 and ("nothing to commit" in proc.stdout or "nothing to commit" in proc.stderr):
			push_proc = subprocess.run(f'git -C "{current_dir}" push origin main', shell=True, env=git_env, text=True, capture_output=True, timeout=25)
			return jsonify({
				"success": True,
				"message": "✅ 模板与文件已经是最新状态，远程 Git 已同步！",
				"details": push_proc.stdout or push_proc.stderr
			})
		elif proc.returncode == 0:
			return jsonify({
				"success": True,
				"message": "🎉 成功将最新模板和修改提交并推送到 GitHub 远程仓库！",
				"details": proc.stdout
			})
		else:
			err_msg = proc.stderr or proc.stdout
			return jsonify({"success": False, "error": f"Git Push 失败: {err_msg}"})
	except Exception as e:
		return jsonify({"success": False, "error": f"执行 Git Push 出错: {str(e)}"})

# ==========================================
# 4. Reusable Quick Templates APIs
# ==========================================

@app.route("/api/templates", methods=["GET"])
def get_templates():
	"""Retrieves all reusable task templates."""
	try:
		conn = get_db_connection()
		cursor = conn.cursor()
		cursor.execute("SELECT * FROM templates ORDER BY id DESC")
		rows = cursor.fetchall()
		conn.close()
		return jsonify({"success": True, "templates": [dict(r) for r in rows]})
	except Exception as e:
		return jsonify({"success": False, "error": str(e)})

@app.route("/api/templates", methods=["POST"])
def create_template():
	"""Creates a new reusable task template and auto-syncs to Git."""
	try:
		data = request.json or {}
		name = data.get("name", "").strip()
		category = data.get("category", "日常任务").strip()
		assignee = data.get("assignee", "全员").strip()
		content = data.get("content", "").strip()
		requirements = data.get("requirements", "").strip()
		reward_flowers = int(data.get("reward_flowers", 1))

		if not name or not content:
			return jsonify({"success": False, "error": "模板名称和内容不能为空"})

		conn = get_db_connection()
		cursor = conn.cursor()
		cursor.execute("""
			INSERT INTO templates (name, category, assignee, content, requirements, reward_flowers)
			VALUES (?, ?, ?, ?, ?, ?)
		""", (name, category, assignee, content, requirements, reward_flowers))
		conn.commit()
		conn.close()

		auto_git_sync_templates()

		return jsonify({"success": True, "message": "💾 模板保存成功并自动同步至 Git！"})
	except Exception as e:
		return jsonify({"success": False, "error": str(e)})

@app.route("/api/templates/<int:template_id>", methods=["DELETE"])
def delete_template(template_id):
	"""Deletes a task template and auto-syncs to Git."""
	try:
		conn = get_db_connection()
		cursor = conn.cursor()
		cursor.execute("DELETE FROM templates WHERE id = ?", (template_id,))
		conn.commit()
		conn.close()

		auto_git_sync_templates()

		return jsonify({"success": True, "message": "🗑️ 模板已成功删除并自动同步至 Git"})
	except Exception as e:
		return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
	try:
		reconfig = getattr(sys.stdout, "reconfigure", None)
		if callable(reconfig):
			reconfig(line_buffering=True)
	except Exception:
		pass

	host = config_data.get("host", "0.0.0.0")
	port = int(config_data.get("port", 5089))
	extra_ip = config_data.get("extra_access_ip", "192.168.31.13")
	local_ips = get_all_local_ips()

	print("=" * 65, flush=True)
	print("🏆 安仔 恩妞任务小分队系统 (Task Force Hub) 已就绪启动", flush=True)
	print(f"📍 本地访问地址: http://localhost:{port}", flush=True)
	print(f"📍 本地 127 地址: http://127.0.0.1:{port}", flush=True)
	if extra_ip:
		print(f"📍 31网段手机/iPad/电脑访问(端口映射入口): http://{extra_ip}:{port} ⭐", flush=True)
	print(f"📍 0网段本地直连地址: http://192.168.0.25:{port}", flush=True)
	if local_ips:
		for ip in local_ips:
			if ip not in ["192.168.0.25", extra_ip]:
				print(f"📍 局域网网卡 IP: http://{ip}:{port}", flush=True)
	print("=" * 65, flush=True)
	app.run(host=host, port=port, debug=False, threaded=True)
