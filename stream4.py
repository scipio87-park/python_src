import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import text # SQL 실행을 위해 필요

# --- DB 연결 (Neon/Postgres) ---
conn = st.connection("postgresql", type="sql")

if st.session_state.get('logged_in'):
    # 사이드바 메뉴 및 [기능 1] 검색창 추가
    menu = ["목록", "글쓰기"]
    choice = st.sidebar.selectbox("메뉴", menu)
    
    st.sidebar.divider()
    search_query = st.sidebar.text_input("🔍 글 검색", placeholder="제목 또는 작성자 검색")

    # [수정 모드] - 기존 코드 유지
    if st.session_state.get('edit_mode'):
        st.subheader("📝 수정하기")
        pid = st.session_state['edit_post_id']
        p_data = conn.query(f"SELECT title, content FROM posts WHERE id={pid}", ttl=0).iloc[0]
        new_title = st.text_input("제목", value=p_data['title'])
        new_content = st.text_area("내용", value=p_data['content'])
        
        if st.button("수정 완료"):
            with conn.session as s:
                s.execute(text("UPDATE posts SET title=:t, content=:c WHERE id=:id"), 
                          {"t": new_title, "c": new_content, "id": pid})
                s.commit()
            st.session_state.update({'edit_mode': False, 'edit_post_id': None})
            st.rerun()

    # [글쓰기 모드] - [기능 2] 이미지 미리보기 추가
    elif choice == "글쓰기":
        st.subheader("✍️ 새 글 작성")
        t = st.text_input("제목")
        cont = st.text_area("내용")
        
        # 이미지 업로드 및 미리보기 로직
        f = st.file_uploader("이미지 첨부", type=['png', 'jpg', 'jpeg'])
        if f is not None:
            st.image(f, caption="이미지 미리보기", width=300) # 즉시 미리보기
        
        if st.button("등록"):
            fname = f.name if f else None
            fdata = f.read() if f else None
            with conn.session as s:
                s.execute(text("INSERT INTO posts(author, title, content, file_name, file_data, date) VALUES (:a, :t, :c, :fn, :fd, :d)"),
                          {"a": st.session_state['username'], "t": t, "c": cont, "fn": fname, "fd": fdata, "d": datetime.now().strftime("%Y-%m-%d %H:%M")})
                s.commit()
            st.success("등록되었습니다!")
            st.rerun()

    # [목록 모드] - [기능 3] 검색 필터링 적용
    elif choice == "목록":
        st.subheader("📋 게시글 목록")
        # 데이터 호출
        posts = conn.query("SELECT * FROM posts ORDER BY id DESC", ttl=0)
        
        # 검색어 필터링 적용 (Pandas 활용)
        if search_query:
            posts = posts[
                posts['title'].str.contains(search_query, case=False, na=False) |
                posts['author'].str.contains(search_query, case=False, na=False)
            ]

        if posts.empty:
            st.info("검색 결과가 없거나 게시글이 존재하지 않습니다.")
        else:
            for _, row in posts.iterrows():
                with st.expander(f"📌 {row['title']} (by {row['author']})"):
                    # 이미지가 있다면 표시
                    if row['file_data']:
                        st.image(row['file_data'], use_container_width=True)
                    
                    st.write(row['content'])
                    
            
                    # --- [좋아요 기능 시작] ---
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        # 현재 사용자가 이 글에 좋아요를 눌렀는지 확인
                        check_like = conn.query(
                            f"SELECT * FROM likes_log WHERE post_id={row['id']} AND username='{st.session_state['username']}'", 
                            ttl=0
                        )
                        
                        is_liked = not check_like.empty
                        btn_label = f"❤️ {row['likes']}" if is_liked else f"🤍 {row['likes']}"
                        
                        if st.button(btn_label, key=f"like_{row['id']}"):
                            with conn.session as s:
                                if is_liked:
                                    # 이미 눌렀다면 좋아요 취소
                                    s.execute(text("DELETE FROM likes_log WHERE post_id=:pid AND username=:u"), 
                                            {"pid": row['id'], "u": st.session_state['username']})
                                    s.execute(text("UPDATE posts SET likes = likes - 1 WHERE id=:pid"), {"pid": row['id']})
                                else:
                                    # 처음 누르는 거라면 좋아요 추가
                                    s.execute(text("INSERT INTO likes_log (post_id, username) VALUES (:pid, :u)"), 
                                            {"pid": row['id'], "u": st.session_state['username']})
                                    s.execute(text("UPDATE posts SET likes = likes + 1 WHERE id=:pid"), {"pid": row['id']})
                                s.commit()
                            st.rerun() # 상태 반영을 위해 새로고침
                    # --- [좋아요 기능 끝] ---
                    
                    
                    
                    # 다운로드 버튼 (기존 유지)
                    if row['file_name']:
                        st.download_button("📁 파일 다운로드", row['file_data'], row['file_name'], key=f"dl_{row['id']}")
                    
                    # 수정/삭제 버튼 (기존 유지)
                    if st.session_state['username'] == row['author']:
                        c1, c2, _, _, _ = st.columns(5)
                        with c1:
                            if st.button("수정", key=f"e_{row['id']}"):
                                st.session_state.update({'edit_mode': True, 'edit_post_id': row['id']})
                                st.rerun()
                        with c2:
                            if st.button("삭제", key=f"d_{row['id']}"):
                                with conn.session as s:
                                    s.execute(text(f"DELETE FROM posts WHERE id={row['id']}"))
                                    s.commit()
                                st.rerun()
                    
                    # 댓글 (기존 유지)
                    st.divider()
                    st.caption("💬 댓글")
                    coms = conn.query(f"SELECT * FROM comments WHERE post_id={row['id']}", ttl=0)
                    for _, cm in coms.iterrows():
                        st.write(f"**{cm['author']}**: {cm['comment']}")
                    
                    with st.form(key=f"f_{row['id']}", clear_on_submit=True):
                        nc = st.text_input("댓글 작성")
                        if st.form_submit_button("등록"):
                            with conn.session as s:
                                s.execute(text("INSERT INTO comments(post_id, author, comment, date) VALUES (:pid, :a, :c, :d)"),
                                          {"pid": row['id'], "a": st.session_state['username'], "c": nc, "d": datetime.now().strftime("%H:%M")})
                                s.commit()
                            st.rerun()
else:
    st.warning("로그인 후 이용 가능합니다.")



