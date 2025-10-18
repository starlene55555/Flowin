# =============================================================================
# Streamlit：AI 任務排程（模擬版）
# 說明：
# - 完全模擬 AI 行為（無需 API key）
# - 主頁（任務 / 目標）分頁式顯示，預設在任務
# - 任務含截止日期與截止時間
# - 日曆頁可新增固定行程，AI 排任務會避開這些時間（模擬）
# - 底部固定「開始行程」按鈕 -> 進入專注全螢幕模式
# - 專注模式可暫停或完成任務；完成後跳出回饋對話框（取代個人化優化）
# =============================================================================

import streamlit as st
import datetime
import random
from collections import defaultdict

# -------------------------
# 頁面與樣式設定
# -------------------------
st.set_page_config(
    page_title="AI 任務排程（模擬）",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 輕微 CSS：藍色按鈕風格與固定底部欄位（開始行程）
st.markdown(
    """
    <style>
    /* 按鈕風格 */
    .stButton>button {
        background: #0a66c2;
        color: white;
        border-radius: 8px;
        padding: 10px 18px;
    }
    .stButton>button:hover {
        opacity: 0.9;
    }
    /* 固定底部容器 */
    .fixed-footer {
        position: fixed;
        left: 0;
        bottom: 10px;
        width: 100%;
        display: flex;
        justify-content: center;
        z-index: 9999;
        pointer-events: none;
    }
    .fixed-footer .stButton>button {
        pointer-events: auto;
        font-size: 18px;
    }
    /* 專注模式標題 */
    .focus-title {
        font-size: 34px;
        font-weight: 700;
        color: #0a66c2;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# -------------------------
# 初始化 session_state（儲存所有資料）
# -------------------------
if "page" not in st.session_state:
    st.session_state.page = "home"  # home / calendar / focus
if "tasks" not in st.session_state:
    st.session_state.tasks = []  # 每項 task: dict{name, deadline_date, deadline_time, description, created_at}
if "events" not in st.session_state:
    st.session_state.events = []  # 固定行程 (title, date, start_time, duration_minutes)
if "schedule" not in st.session_state:
    st.session_state.schedule = []  # AI 生成的 schedule: list of dict{task, datetime, duration}
if "current_schedule_index" not in st.session_state:
    st.session_state.current_schedule_index = 0
if "feedbacks" not in st.session_state:
    st.session_state.feedbacks = []  # 儲存任務回饋
if "welcome_shown" not in st.session_state:
    st.session_state.welcome_shown = True
if "goals" not in st.session_state:
    st.session_state.goals = []  # 儲存目標列表


# -------------------------
# 工具函式（模擬 AI 排程邏輯）
# -------------------------
def estimate_task_total_minutes(task_name, description):
    """
    模擬估算任務總耗時（分鐘）。
    簡單 heuristic：基於名稱長度與描述長度作估算，加隨機波動。
    """
    base = 60  # 基本一小時
    name_factor = max(0, len(task_name)) * 1  # 每個字大約加 1 分鐘
    desc_factor = max(0, len(description)) * 0.5  # 每字 0.5 分鐘
    noise = random.randint(-15, 30)
    total = int(base + name_factor + desc_factor + noise)
    return max(20, total)  # 最少 20 分鐘


def is_conflict_with_events(dt_start, duration_minutes, events):
    """
    判斷 dt_start 開始的時段是否與固定 events 衝突。
    events: list of dict {title, date (date), start_time (time), duration}
    """
    dt_end = dt_start + datetime.timedelta(minutes=duration_minutes)
    for e in events:
        e_start = datetime.datetime.combine(e["date"], e["start_time"])
        e_end = e_start + datetime.timedelta(minutes=e["duration"])
        # 若兩者時間重疊即視為衝突
        if not (dt_end <= e_start or dt_start >= e_end):
            return True
    return False


def generate_simulated_schedule(tasks, events):
    """
    模擬 AI：根據 tasks 與固定 events 生成 schedule。
    原則：
    - 每個 task 估算 total_minutes，切成若干段 (30/45/60)
    - 嘗試安排於今日起的未來 7 天內，避開 events 的固定時段
    - 簡單分配：從最近日期往後填滿
    """
    schedule = []
    today = datetime.date.today()
    # 先把 events 轉成容易檢查的格式（已在 events 中）
    for t in tasks:
        total_min = estimate_task_total_minutes(t["name"], t.get("description", ""))
        # 切割策略：優先用 60 或 45，剩下用 30
        remaining = total_min
        sub_id = 1
        # 產生子任務直到 remaining <= 0
        while remaining > 0:
            # 選取段長
            if remaining >= 90:
                seg = 90
            elif remaining >= 60:
                seg = 60
            elif remaining >= 45:
                seg = 45
            else:
                seg = 30
            # 找時間槽：從今天算起的 14 天內嘗試找到一個非衝突時段
            placed = False
            for day_offset in range(0, 14):  # 兩週的彈性
                candidate_date = today + datetime.timedelta(days=day_offset)
                # 預設可接受時段為 9:00 - 22:00，嘗試每小時起始
                for hour in range(9, 22):
                    candidate_dt = datetime.datetime.combine(candidate_date, datetime.time(hour=hour, minute=0))
                    # 檢查是否衝突（對於簡單示範，我們只避開 events）
                    if not is_conflict_with_events(candidate_dt, seg, events):
                        # 若此時間點已被其他子任務佔用，也要避免：檢查 schedule 中是否有衝突
                        if not any(not (
                                candidate_dt + datetime.timedelta(minutes=seg) <= s["start"] or candidate_dt >= s[
                            "end"]) for s in schedule):
                            # 放進 schedule
                            schedule.append({
                                "task_name": t["name"],
                                "subtask_id": sub_id,
                                "start": candidate_dt,
                                "end": candidate_dt + datetime.timedelta(minutes=seg),
                                "duration": seg,
                                "deadline": datetime.datetime.combine(t["deadline_date"], t["deadline_time"]),
                                "description": t.get("description", "")
                            })
                            placed = True
                            break
                if placed:
                    break
            # 若沒有找到時間槽（極少見），就把它塞在最後可排的時段（今天+14）
            if not placed:
                fallback_dt = datetime.datetime.combine(today + datetime.timedelta(days=14),
                                                        datetime.time(hour=9, minute=0))
                schedule.append({
                    "task_name": t["name"],
                    "subtask_id": sub_id,
                    "start": fallback_dt,
                    "end": fallback_dt + datetime.timedelta(minutes=seg),
                    "duration": seg,
                    "deadline": datetime.datetime.combine(t["deadline_date"], t["deadline_time"]),
                    "description": t.get("description", "")
                })
            remaining -= seg
            sub_id += 1
    # 排序 schedule
    schedule = sorted(schedule, key=lambda x: x["start"])
    # 轉成易讀格式：加上 index
    for idx, item in enumerate(schedule):
        item["idx"] = idx
    return schedule


# -------------------------
# 頁面切換小工具
# -------------------------
def set_page(new_page):
    st.session_state.page = new_page


# -------------------------
# 主畫面（home）Section：歡迎語 + 任務/目標左右切換
# -------------------------
def section_home():
    st.header("👋 今天你有什麼任務或目標要達成呢？")
    # 左右選單：用 columns 模擬
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🔵 任務", key="btn_task"):
            set_page("home_tasks")  # 內部子頁面
    with col2:
        if st.button("🟢 目標", key="btn_goal"):
            set_page("home_goals")

    # 內容區（根據 page 狀態顯示任務或目標）
    st.markdown("---")
    if st.session_state.page == "home_goals":
        show_goal_input()
    else:
        # 預設為任務
        show_task_input()


def show_task_input():
    """任務輸入表單（包含截止日期與截止時間）"""
    st.subheader("新增任務（任務會由 AI 模擬拆解並安排）")
    with st.form("task_input_form"):
        name = st.text_input("任務名稱（例：心理學報告）", max_chars=120)
        description = st.text_area("任務描述（可選）", help="可描述要求、字數、考試範圍等")
        # 日期與時間
        dl_date = st.date_input("截止日期", datetime.date.today() + datetime.timedelta(days=7))
        dl_time = st.time_input("截止時間", datetime.time(hour=23, minute=59))
        submitted = st.form_submit_button("新增任務")
        if submitted:
            if not name.strip():
                st.warning("請輸入任務名稱")
            else:
                st.session_state.tasks.append({
                    "name": name.strip(),
                    "description": description.strip(),
                    "deadline_date": dl_date,
                    "deadline_time": dl_time,
                    "created_at": datetime.datetime.now()
                })
                st.success(f"✅ 已新增任務：{name.strip()}")
                # 清空子畫面預設維持在任務
                st.session_state.page = "home"

    # 顯示已登記的任務（只有在有任務時顯示）
    if st.session_state.tasks:
        st.subheader("目前任務清單")
        for i, t in enumerate(st.session_state.tasks):
            dl_str = f"{t['deadline_date'].strftime('%Y-%m-%d')} {t['deadline_time'].strftime('%H:%M')}"
            st.write(f"{i + 1}. **{t['name']}** ｜ 截止：{dl_str} ｜ 描述：{t.get('description', '（無）')}")


def show_goal_input():
    """目標輸入與四象限分類（UI 顯示，AI 會模擬分類）"""
    st.subheader("設定目標（AI 會模擬分類為長期/短期與重要/緊急）")
    with st.form("goal_input_form"):
        goal_text = st.text_area("輸入你的目標（例：期末考拿高分）")
        goal_horizon = st.selectbox("目標時程", ["短期", "長期"])
        submitted = st.form_submit_button("新增目標")
        if submitted:
            if not goal_text.strip():
                st.warning("請輸入目標內容")
            else:
                # 模擬 AI 分類（簡單隨機或基於文字長度）
                importance = "重要" if len(goal_text) > 10 or "拿" in goal_text else "一般"
                urgency = "緊急" if goal_horizon == "短期" else "非緊急"
                st.session_state.goals.append({
                    "text": goal_text.strip(),
                    "horizon": goal_horizon,
                    "importance": importance,
                    "urgency": urgency
                })
                st.success("✅ 已新增目標，AI 已完成初步分類（模擬）")

    # 顯示目標清單
    if "goals" in st.session_state and st.session_state.goals:
        st.subheader("目標清單（AI 模擬分類）")
        for i, g in enumerate(st.session_state.goals):
            st.write(f"{i + 1}. {g['text']} ｜ {g['horizon']} ｜ {g['importance']} / {g['urgency']}")


# -------------------------
# 日曆頁面 Section：顯示 schedule 與新增固定行程（events）
# -------------------------
def section_calendar():
    st.header("📆 行事曆（固定行程 / 已排任務）")
    # 右上新增事件
    col_l, col_r = st.columns([4, 1])
    with col_r:
        if st.button("➕ 新增固定行程"):
            st.session_state.show_add_event = True

    # 新增事件的表單（以 modal 或 expander 表示）
    if st.session_state.get("show_add_event", False):
        with st.form("add_event_form"):
            title = st.text_input("行程標題")
            date = st.date_input("日期")
            start_str = st.text_input("開始時間 (HH:MM)", value="09:00")  # 使用者直接輸入
            end_str = st.text_input("結束時間 (HH:MM)", value="10:00")  # 使用者直接輸入
            submitted_ev = st.form_submit_button("新增行程")

            if submitted_ev:
                try:
                    start_time = datetime.datetime.strptime(start_str, "%H:%M").time()
                    end_time = datetime.datetime.strptime(end_str, "%H:%M").time()
                except ValueError:
                    st.warning("請輸入正確格式 HH:MM")
                else:
                    if not title.strip():
                        st.warning("請輸入行程標題")
                    else:
                        # 計算 duration
                        duration_minutes = int(
                            (datetime.datetime.combine(date, end_time) - datetime.datetime.combine(date,
                                                                                                   start_time)).total_seconds() / 60
                        )
                        st.session_state.events.append({
                            "title": title.strip(),
                            "date": date,
                            "start_time": start_time,
                            "end_time": end_time,
                            "duration": duration_minutes
                        })
                        st.success(f"✅ 已新增固定行程：{title} ({start_time} - {end_time})")
                        st.session_state.show_add_event = False

    # 顯示固定行程
    if st.session_state.events:
        st.subheader("固定行程")
        for e in st.session_state.events:
            st.write(
                f"- {e['date'].strftime('%Y-%m-%d')} {e['start_time'].strftime('%H:%M')}（{e['duration']} 分）｜{e['title']}")
    else:
        st.info("目前尚無固定行程，可使用右上角「新增固定行程」建立。")

    st.markdown("---")
    # 顯示已排的 AI 行程（若有）
    if st.session_state.schedule:
        st.subheader("AI 已排任務（模擬）")
        # 分日期顯示
        grouped = defaultdict(list)
        for s in st.session_state.schedule:
            date_key = s["start"].date()
            grouped[date_key].append(s)
        for date_key in sorted(grouped.keys()):
            st.write(f"### {date_key.strftime('%Y-%m-%d')}")
            for item in grouped[date_key]:
                st.write(
                    f"- {item['start'].strftime('%H:%M')} ~ {item['end'].strftime('%H:%M')} ｜ {item['task_name']} （{item['duration']} 分）")
    else:
        st.info("尚未由 AI 生成排程。請回到主頁新增任務後按「由 AI 生成排程」。")


# -------------------------
# 專注模式 Section（全螢幕顯示當前任務）
# -------------------------
def section_focus_mode():
    # 進入專注模式：只顯示當前 schedule 中的項目
    if not st.session_state.schedule:
        st.info("目前沒有可執行的任務，請先回到主頁新增任務並由 AI 生成排程。")
        return

    idx = st.session_state.current_schedule_index
    if idx >= len(st.session_state.schedule):
        st.info("所有任務已完畢。")
        return

    current = st.session_state.schedule[idx]
    # 顯示當前任務（大字）
    st.markdown(f"<div class='focus-title'>🔥 當前任務：{current['task_name']}（子任務 {current['subtask_id']}）</div>",
                unsafe_allow_html=True)
    st.write(f"開始時間：{current['start'].strftime('%Y-%m-%d %H:%M')}")
    st.write(f"預計時長：{current['duration']} 分鐘")
    st.write("---")
    # 模擬倒數計時（非嚴謹計時，只示意）
    st.info("此處為模擬專注畫面。按下「暫停任務」或「任務完成」來結束此工作段。")

    # AI 對話模式（向下滑或開啟）：這裡用按鈕或展開區塊模擬
    with st.expander("💬 與 AI 對話（模擬）"):
        st.write("你可以在此詢問 AI 有關此子任務的協助（模擬回覆）。")
        user_msg = st.text_input("輸入訊息給 AI", key="ai_chat_input")
        if st.button("送出訊息", key="ai_send"):
            if user_msg.strip():
                # 模擬回覆邏輯：簡單回覆或提供步驟
                reply = simulate_ai_reply(user_msg, current)
                st.markdown(f"**AI 回覆：** {reply}")
            else:
                st.warning("請先輸入訊息。")

    # 暫停或完成按鈕
    col1, col2 = st.columns(2)
    with col1:
        if st.button("暫停任務"):
            # 跳出回饋 modal
            open_feedback_modal(current, status="暫停")
    with col2:
        if st.button("任務完成"):
            open_feedback_modal(current, status="完成")


def simulate_ai_reply(user_msg, current_task):
    """
    一個簡單的模擬 AI 回覆：根據使用者訊息中關鍵詞回應。
    只是示範用途，不呼叫外部 API。
    """
    msg = user_msg.lower()
    if "結構" in msg or "大綱" in msg:
        return "建議先列出三個重點段落，再對每段寫 5 個句子作為草稿輪廓。"
    if "怎麼開始" in msg or "從哪裡" in msg:
        return "從整理題目要求與抓 3 個關鍵字開始，然後搜尋 2 篇相關參考資料。"
    if "時間" in msg or "多久" in msg:
        return f"依目前子任務預估約 {current_task['duration']} 分鐘，建議設定番茄鐘（25/5）。"
    # 預設回覆
    return "我建議先把任務拆成小段，設定短時間專注完成第一段，再回來檢視成效。"


# 回饋 Modal（使用 st.modal，如果版本支援）
def open_feedback_modal(current_task, status="完成"):
    """
    彈出回饋視窗：詢問「此次任務順利嗎？有什麼想法嗎？」
    回饋會被儲存在 st.session_state.feedbacks
    """
    modal_title = f"任務 {status} — 回饋"
    # st.modal 在某些舊版 streamlit 可能不存在，改用 st.empty + form 模擬
    try:
        with st.modal(modal_title):
            st.write(f"此次任務：**{current_task['task_name']}（子任務 {current_task['subtask_id']}）**")
            success = st.radio("此次任務順利嗎？", ["順利", "遇到困難"], index=0)
            comments = st.text_area("有什麼想法或回饋？（可選）")
            if st.button("送出回饋"):
                st.session_state.feedbacks.append({
                    "task_name": current_task['task_name'],
                    "subtask_id": current_task['subtask_id'],
                    "status": status,
                    "success": success,
                    "comments": comments,
                    "timestamp": datetime.datetime.now()
                })
                st.success("感謝你的回饋！AI 會根據這些資訊（模擬）改善未來安排。")
                # 若按完成，自動前進到下一個子任務
                if status == "完成":
                    st.session_state.current_schedule_index += 1
                    # 若超過 schedule 長度，reset
                    if st.session_state.current_schedule_index >= len(st.session_state.schedule):
                        st.session_state.current_schedule_index = len(st.session_state.schedule)
                # 關閉 modal 自動返回
    except Exception:
        # 若沒有 st.modal（舊版），用簡單的 form 代替（頁面區塊處理）
        with st.form("feedback_fallback"):
            st.write(f"此次任務：**{current_task['task_name']}（子任務 {current_task['subtask_id']}）**")
            success = st.radio("此次任務順利嗎？", ["順利", "遇到困難"], index=0)
            comments = st.text_area("有什麼想法或回饋？（可選）")
            submitted_fb = st.form_submit_button("送出回饋（備援）")
            if submitted_fb:
                st.session_state.feedbacks.append({
                    "task_name": current_task['task_name'],
                    "subtask_id": current_task['subtask_id'],
                    "status": status,
                    "success": success,
                    "comments": comments,
                    "timestamp": datetime.datetime.now()
                })
                st.success("感謝你的回饋（備援方式）！")
                if status == "完成":
                    st.session_state.current_schedule_index += 1
                    if st.session_state.current_schedule_index >= len(st.session_state.schedule):
                        st.session_state.current_schedule_index = len(st.session_state.schedule)


# -------------------------
# 主要頁面流程（根據 st.session_state.page 切換）
# -------------------------
def main():
    # 上方主選單（home / calendar / focus）
    top_col1, top_col2, top_col3 = st.columns([1, 1, 1])
    with top_col1:
        if st.button("🏠 主頁"):
            set_page("home")
    with top_col2:
        if st.button("📆 行事曆"):
            set_page("calendar")
    with top_col3:
        if st.button("🎯 專注模式"):
            set_page("focus")

    st.markdown("---")

    # 根據頁面顯示內容
    if st.session_state.page in ["home", "home_goals", "home_tasks"]:
        # show welcome + home content
        section_home()
        # 下方提供一個按鈕，讓使用者觸發 AI 生成排程（模擬）
        st.markdown("---")
        st.subheader("由 AI 生成排程（模擬）")
        if st.button("🪄 由 AI 生成排程（模擬）"):
            if not st.session_state.tasks:
                st.warning("請先新增至少一項任務。")
            else:
                st.session_state.schedule = generate_simulated_schedule(st.session_state.tasks, st.session_state.events)
                st.session_state.current_schedule_index = 0
                st.success("AI 已生成排程（模擬）。你可以到「行事曆」頁或點下方「開始行程」進入專注模式。")
        # 顯示少量已排結果（一旦生成才顯示）
        if st.session_state.schedule:
            st.subheader("快速預覽：未來三個子任務")
            for s in st.session_state.schedule[:3]:
                st.write(f"- {s['start'].strftime('%Y-%m-%d %H:%M')} ｜ {s['task_name']}（{s['duration']} 分）")
    elif st.session_state.page == "calendar":
        section_calendar()
    elif st.session_state.page == "focus":
        section_focus_mode()
    else:
        st.write("未知頁面")

    # 永遠固定在畫面最下方的「開始行程」按鈕（使用 CSS fixed-footer）
        # 永遠固定在畫面最下方的「開始行程」按鈕（使用 CSS fixed-footer）
        footer_html = """
        <div class="fixed-footer">
            <form action="#" method="post">
        """
        # 使用 st.button 以外的方式無法觸發 streamlit callback，所以把按鈕放在頁面上同時用 st.button 作為主要事件
        st.markdown(footer_html, unsafe_allow_html=True)
        if st.button("▶️ 開始行程"):
            # 若尚未生成 schedule，提示使用者
            if not st.session_state.schedule:
                st.warning("尚未生成排程，請先在主頁按「由 AI 生成排程（模擬）」。")
            else:
                set_page("focus")
        st.markdown("</form></div>", unsafe_allow_html=True)

    # 顯示一些開發用的快速資訊（可隱藏）
    with st.expander("開發者資訊（模擬資料）", expanded=False):
        st.write("已儲存任務數：", len(st.session_state.tasks))
        st.write("已儲存固定行程數：", len(st.session_state.events))
        st.write("排程項目數：", len(st.session_state.schedule))
        st.write("回饋紀錄：", st.session_state.feedbacks)


# Run app
if __name__ == "__main__":
    main()
