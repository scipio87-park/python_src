import streamlit as st
import sqlite3
import pandas as pd
import hashlib
from datetime import datetime

# --- DB 설정 ---
def init_db():
    conn = sqlite3.connect('board.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS posts 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, author TEXT, title TEXT, 
                  content TEXT, file_name TEXT, file_data BLOB, date TEXT)''')
          
    c.execute('CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER, author TEXT, comment TEXT, date TEXT)')
    conn.commit()
    return conn

conn = init_db()
c = conn.cursor()

def hash_pass(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- 세션 상태 초기화 ---
if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'username': "", 'edit_mode': False, 'edit_post_id': None})

# --- 사이드바 로그인 ---
with st.sidebar:
    if not st.session_state['logged_in']:
        auth_mode = st.radio("접속", ["로그인", "회원가입"])
        user = st.text_input("ID")
        pw = st.text_input("PW", type="password")
        if st.button("확인"):
            if auth_mode == "로그인":
                c.execute('SELECT * FROM users WHERE username=? AND password=?', (user, hash_pass(pw)))
                if c.fetchone():
                    st.session_state.update({'logged_in': True, 'username': user})
                    st.rerun()
                else: st.error("실패!")
            else:
                try:
                    c.execute('INSERT INTO users VALUES (?,?)', (user, hash_pass(pw)))
                    conn.commit()
                    st.success("가입 완료!")
                except: st.error("중복 ID")
    else:
        st.write(f"👤 **{st.session_state['username']}**님")
        if st.button("로그아웃"):
            st.session_state.update({'logged_in': False, 'username': ""})
            st.rerun()

# --- 메인 로직 ---
st.title("🚀 스마트 게시판")

if st.session_state['logged_in']:
    menu = ["목록", "글쓰기"]
    choice = st.sidebar.selectbox("메뉴", menu)

    # --- 수정 모드 UI ---
    if st.session_state['edit_mode']:
        st.subheader("📝 게시글 수정하기")
        post_id = st.session_state['edit_post_id']
        c.execute('SELECT title, content FROM posts WHERE id=?', (post_id,))
        p_data = c.fetchone()
        
        new_title = st.text_input("제목 변경", value=p_data[0])
        new_content = st.text_area("내용 변경", value=p_data[1], height=200)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("저장"):
                c.execute('UPDATE posts SET title=?, content=? WHERE id=?', (new_title, new_content, post_id))
                conn.commit()
                st.session_state.update({'edit_mode': False, 'edit_post_id': None})
                st.success("수정되었습니다!")
                st.rerun()
        with col2:
            if st.button("취소"):
                st.session_state.update({'edit_mode': False, 'edit_post_id': None})
                st.rerun()

    # --- 일반 메뉴 UI ---
    elif choice == "글쓰기":
        t = st.text_input("제목")
        cont = st.text_area("내용")
        f = st.file_uploader("파일")
        if st.button("등록"):
            fname = f.name if f else None
            fdata = f.read() if f else None
            c.execute('INSERT INTO posts(author, title, content, file_name, file_data, date) VALUES (?,?,?,?,?,?)',
                      (st.session_state['username'], t, cont, fname, fdata, datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()
            st.rerun()

    elif choice == "목록":
        posts = pd.read_sql_query("SELECT * FROM posts ORDER BY id DESC", conn)
        for _, row in posts.iterrows():
            with st.expander(f"📌 {row['title']} (by {row['author']})"):
                st.write(row['content'])
                if row['file_name']:
                    st.download_button("📁 다운로드", row['file_data'], row['file_name'], key=f"dl_{row['id']}")
                
                # 작성자 전용 권한
                if st.session_state['username'] == row['author']:
                    c1, c2, c3, c4, c5 = st.columns(5)
                    with c1:
                        if st.button("수정", key=f"e_{row['id']}"):
                            st.session_state.update({'edit_mode': True, 'edit_post_id': row['id']})
                            st.rerun()
                    with c2:
                        if st.button("삭제", key=f"d_{row['id']}"):
                            c.execute('DELETE FROM posts WHERE id=?', (row['id'],))
                            conn.commit()
                            st.rerun()
                
                # 댓글 섹션
                st.divider()
                st.caption("💬 댓글")
                coms = pd.read_sql_query(f"SELECT * FROM comments WHERE post_id={row['id']}", conn)
                for _, cm in coms.iterrows():
                    st.write(f"**{cm['author']}**: {cm['comment']}")
                
                with st.form(key=f"f_{row['id']}", clear_on_submit=True):
                    nc = st.text_input("댓글 작성")
                    if st.form_submit_button("등록"):
                        c.execute('INSERT INTO comments(post_id, author, comment, date) VALUES (?,?,?,?)',
                                  (row['id'], st.session_state['username'], nc, datetime.now().strftime("%H:%M")))
                        conn.commit()
                        st.rerun()
else:
    st.warning("로그인이 필요한 서비스입니다.")
    
    
      





