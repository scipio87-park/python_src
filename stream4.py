import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime
from sqlalchemy import text

# --- 1. DB 연결 (Neon/Postgres) ---
conn = st.connection("postgresql", type="sql")

# --- 2. DB 테이블 초기화 (최초 실행 시) ---
def init_db():
    with conn.session as s:
        try:
            # Wrap everything in a transaction block
            with s.begin():
                s.execute(text('DROP TABLE likes_log'))                
                s.execute(text('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)'))
                s.execute(text('''CREATE TABLE IF NOT EXISTS posts 
                                 (id SERIAL PRIMARY KEY, author TEXT, title TEXT, 
                                  content TEXT, file_name TEXT, file_data BYTEA, 
                                  date TEXT, likes INTEGER DEFAULT 0)'''))
                s.execute(text('CREATE TABLE IF NOT EXISTS comments (id SERIAL PRIMARY KEY, post_id INTEGER, author TEXT, comment TEXT, date TEXT)'))
                s.execute(text('CREATE TABLE IF NOT EXISTS likes_log (post_id INTEGER, username TEXT, PRIMARY KEY(post_id, username))'))
            # s.commit() is handled automatically by with s.begin()
            s.commit()            
        except Exception as e:
            st.error(f"Database initialization failed: {e}")

init_db()

def hash_pass(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- 3. 세션 상태 초기화 ---
if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'username': "", 'edit_mode': False, 'edit_post_id': None})

# --- 4. 사이드바 (로그인 & 검색) ---
with st.sidebar:
    if not st.session_state['logged_in']:
        st.subheader("🔑 클라우드 접속")
        auth_mode = st.radio("모드 선택", ["로그인", "회원가입"])
        user = st.text_input("아이디")
        pw = st.text_input("비밀번호", type="password")
        
        if st.button("확인"):
            if auth_mode == "로그인":
                res = conn.query(f"SELECT * FROM users WHERE username='{user}' AND password='{hash_pass(pw)}'", ttl=0)
                if not res.empty:
                    st.session_state.update({'logged_in': True, 'username': user})
                    st.rerun()
                else: 
                    st.error("로그인 실패!")
            else:
                try:
                    with conn.session as s:
                        s.execute(text("INSERT INTO users VALUES (:u, :p)"), {"u": user, "p": hash_pass(pw)})
                        s.commit()
                    st.success("회원가입 완료!")
                except: 
                    st.error("이미 존재하는 아이디입니다.")
    else:
        st.write(f"👤 **{st.session_state['username']}**님")
        if st.button("로그아웃"):
            st.session_state.update({'logged_in': False, 'username': ""})
            st.rerun()
        
        st.divider()
        search_query = st.text_input("🔍 글 검색")

# --- 5. 메인 화면 ---
st.title("☁️ Cloud Smart Board")

if st.session_state['logged_in']:
    menu = ["목록", "글쓰기"]
    choice = st.sidebar.selectbox("메뉴", menu)

    # A. 수정 모드
    if st.session_state['edit_mode']:
        pid = st.session_state['edit_post_id']
        p_data = conn.query(f"SELECT title, content FROM posts WHERE id={pid}", ttl=0).iloc[0]
        
        new_title = st.text_input("제목 변경", value=p_data['title'])
        new_content = st.text_area("내용 변경", value=p_data['content'], height=200)
        
        if st.button("수정 완료"):
            with conn.session as s:
                s.execute(text("UPDATE posts SET title=:t, content=:c WHERE id=:id"), 
                          {"t": new_title, "c": new_content, "id": pid})
                s.commit()
            st.session_state.update({'edit_mode': False, 'edit_post_id': None})
            st.rerun()

    # B. 글쓰기 모드
    elif choice == "글쓰기":
        t = st.text_input("제목")
        cont = st.text_area("내용")
        f = st.file_uploader("이미지 첨부", type=['png', 'jpg', 'jpeg'])
        
        #if f: st.image(f, width=300)
        if f: st.image(f, width=30000)   # 2026.02.18 수정     
        

        if st.button("등록"):
            fdata = f.getvalue() if f else None
            with conn.session as s:
                s.execute(text("INSERT INTO posts(author, title, content, file_name, file_data, date) VALUES (:a, :t, :c, :fn, :fd, :d)"),
                          {"a": st.session_state['username'], "t": t, "c": cont, "fn": f.name if f else None, "fd": fdata, "d": datetime.now().strftime("%Y-%m-%d")})
                s.commit()
            st.success("등록 완료!")
            st.rerun()

    # C. 목록 모드
    elif choice == "목록":
        #posts = conn.query("SELECT * FROM posts ORDER BY id DESC", ttl=0)  
        posts = conn.query("SELECT title, author, content FROM posts ORDER BY id DESC", ttl=0)          
        
        if search_query:
            posts = posts[posts['title'].str.contains(search_query, case=False, na=False)]

        for _, row in posts.iterrows():
            with st.expander(f"📌 {row['title']} - {row['author']}"):
                #if row['file_data']:
                #    st.image(row['file_data'])
                st.write(row['content'])
                
                # 좋아요 기능
                #like_res = conn.query(f"SELECT * FROM likes_log WHERE post_id={row['id']} AND username='{st.session_state['username']}'", ttl=0)
                like_res = conn.query(f"SELECT '1' FROM likes_log WHERE post_id={row['id']} AND username='{st.session_state['username']}'", ttl=0)                
                is_liked = not like_res.empty
                
                if st.button(f"{'❤️' if is_liked else '🤍'} {row['likes']}", key=f"lk_{row['id']}"):
                    with conn.session as s:
                        if is_liked:
                            s.execute(text(f"DELETE FROM likes_log WHERE post_id={row['id']} AND username='{st.session_state['username']}'"))
                            s.execute(text(f"UPDATE posts SET likes = likes - 1 WHERE id={row['id']}"))
                        else:
                            s.execute(text(f"INSERT INTO likes_log VALUES ({row['id']}, '{st.session_state['username']}')"))
                            s.execute(text(f"UPDATE posts SET likes = likes + 1 WHERE id={row['id']}"))
                        s.commit()
                    st.rerun()

                # 본인 글 수정/삭제
                if st.session_state['username'] == row['author']:
                    c1, c2 = st.columns(10)[:2] # 작게 배치
                    if c1.button("✏️", key=f"ed_{row['id']}"):
                        st.session_state.update({'edit_mode': True, 'edit_post_id': row['id']})
                        st.rerun()
                    if c2.button("🗑️", key=f"del_{row['id']}"):
                        with conn.session as s:
                            s.execute(text(f"DELETE FROM posts WHERE id={row['id']}"))
                            s.commit()
                        st.rerun()
else:
    st.info("사이드바를 이용해 로그인해 주세요.")
