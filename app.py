# app.py

import streamlit as st
import os
import numpy as np
import pandas as pd
from math import log10, sqrt
import zipfile
import io
import sqlite3
import nibabel as nib  # NIfTI 파일 처리를 위한 라이브러리
import streamlit_authenticator as stauth

# 라이브러리 버전 확인
st.write(f"Streamlit Authenticator 버전: {stauth.__version__}")

# 사용자 정보 설정
names = ['제나희', '최한준', '오주형']
usernames = ['jenahee', 'choihanjun', 'ohjoohyung']
passwords = ['password123', 'password123', 'password123']

# 비밀번호 해시 생성
hashed_passwords = stauth.Hasher(passwords).generate()

# 데이터베이스 초기화 함수
def init_db(db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    # 사용자 비밀번호 변경을 위한 테이블 추가
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_info (
            username TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            psnr REAL NOT NULL,
            FOREIGN KEY(username) REFERENCES user_info(username)
        )
    ''')
    conn.commit()
    conn.close()

# 사용자 정보 로드 또는 초기화
def load_user_info():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT username FROM user_info')
    existing_users = cursor.fetchall()
    if not existing_users:
        # 초기 사용자 정보 설정
        for name, username, hashed_password in zip(names, usernames, hashed_passwords):
            cursor.execute('INSERT INTO user_info (username, name, password) VALUES (?, ?, ?)',
                           (username, name, hashed_password))
        conn.commit()
    else:
        # 기존 사용자들의 비밀번호를 업데이트
        for name, username, hashed_password in zip(names, usernames, hashed_passwords):
            cursor.execute('UPDATE user_info SET password = ? WHERE username = ?', (hashed_password, username))
        conn.commit()
    conn.close()

# 비밀번호 업데이트 함수
def update_password(username, new_hashed_password):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('UPDATE user_info SET password = ? WHERE username = ?', (new_hashed_password, username))
    conn.commit()
    conn.close()

# 리더보드 가져오기 함수
def get_leaderboard(db_file):
    conn = sqlite3.connect(db_file)
    df = pd.read_sql_query('''
        SELECT user_info.name AS 이름, MAX(scores.psnr) AS PSNR
        FROM scores
        JOIN user_info ON scores.username = user_info.username
        GROUP BY scores.username
        ORDER BY PSNR DESC
    ''', conn)
    conn.close()
    return df

# PSNR 계산 함수 (3D 데이터용)
def calculate_psnr(original, generated):
    mse = np.mean((original - generated) ** 2)
    if mse == 0:
        return float('inf')
    max_pixel = np.max(original)
    psnr = 20 * log10(max_pixel / sqrt(mse))
    return psnr

# 메인 함수
def main():
    st.title("NIfTI 파일 제출 및 PSNR 평가")
    st.write("생성한 NIfTI(.nii) 파일을 제출하여 원본 데이터와의 PSNR 점수를 확인하세요.")

    # 데이터베이스 초기화 및 사용자 정보 로드
    global db_file
    db_file = 'scores.db'
    init_db(db_file)
    load_user_info()

    # 인증 객체 생성
    authenticator = stauth.Authenticate(names, usernames, hashed_passwords, 'some_cookie_name', 'some_signature_key', cookie_expiry_days=1)

    # 로그인 위젯
    try:
        name, authentication_status = authenticator.login('로그인')
        st.write(f"login() 함수 반환값: {name}, {authentication_status}")
    except Exception as e:
        st.error(e)
        return

    if authentication_status:
        st.write(f"안녕하세요, {name}님!")

        # 로그아웃 버튼
        authenticator.logout('로그아웃')

        # 현재 사용자 이름(username) 가져오기
        username = usernames[names.index(name)]

        # 비밀번호 변경
        if st.sidebar.button('비밀번호 변경'):
            try:
                new_password = st.sidebar.text_input('새로운 비밀번호를 입력하세요', type='password')
                confirm_password = st.sidebar.text_input('비밀번호 확인', type='password')
                if st.sidebar.button('비밀번호 변경 확인'):
                    if new_password == confirm_password:
                        if len(new_password) >= 6:
                            new_hashed_password = stauth.Hasher([new_password]).generate()[0]
                            update_password(username, new_hashed_password)
                            st.success('비밀번호가 성공적으로 변경되었습니다.')
                            # 인증 정보 업데이트
                            index = usernames.index(username)
                            hashed_passwords[index] = new_hashed_password
                            # 인증 객체 재생성
                            authenticator = stauth.Authenticate(names, usernames, hashed_passwords, 'some_cookie_name', 'some_signature_key', cookie_expiry_days=1)
                        else:
                            st.error('비밀번호는 최소 6자 이상이어야 합니다.')
                    else:
                        st.error('비밀번호가 일치하지 않습니다.')
            except Exception as e:
                st.error(e)

        # NIfTI 파일 업로드
        uploaded_zip = st.file_uploader("생성한 NIfTI 파일들을 압축하여 업로드하세요 (ZIP 파일)", type=["zip"])

        # 원본 NIfTI 파일 로드
        original_data_folder = 'test_nii_files'  # 공개된 테스트 NIfTI 파일 폴더
        if not os.path.exists(original_data_folder):
            st.error(f"원본 NIfTI 파일 폴더 '{original_data_folder}'가 존재하지 않습니다.")
            return
        original_nii_files = [f for f in os.listdir(original_data_folder) if f.endswith('.nii') or f.endswith('.nii.gz')]
        if not original_nii_files:
            st.error("원본 NIfTI 파일이 존재하지 않습니다.")
            return

        if uploaded_zip is not None:
            try:
                # 업로드된 ZIP 파일 읽기
                with zipfile.ZipFile(uploaded_zip) as zip_ref:
                    uploaded_files = zip_ref.namelist()
                    if len(uploaded_files) != len(original_nii_files):
                        st.error(f"NIfTI 파일 개수가 일치하지 않습니다. 원본 NIfTI 파일 개수: {len(original_nii_files)}")
                        return

                    psnr_values = []

                    for original_file in original_nii_files:
                        # 원본 NIfTI 파일 로드
                        original_nii_path = os.path.join(original_data_folder, original_file)
                        original_image = nib.load(original_nii_path).get_fdata()

                        # 대응되는 업로드된 NIfTI 파일 찾기
                        if original_file in uploaded_files:
                            with zip_ref.open(original_file) as file:
                                # 업로드된 파일을 메모리에 로드
                                file_content = file.read()
                                file_like_object = io.BytesIO(file_content)
                                generated_image = nib.load(file_like_object).get_fdata()
                        else:
                            st.error(f"'{original_file}' 파일이 업로드된 ZIP에 포함되어 있지 않습니다.")
                            return

                        # PSNR 계산
                        if original_image.shape != generated_image.shape:
                            st.error(f"'{original_file}' 파일의 데이터 크기가 원본과 일치하지 않습니다.")
                            return

                        psnr = calculate_psnr(original_image, generated_image)
                        psnr_values.append(psnr)

                    # 평균 PSNR 계산
                    average_psnr = sum(psnr_values) / len(psnr_values)

                    # 점수 저장
                    conn = sqlite3.connect(db_file)
                    cursor = conn.cursor()
                    cursor.execute('INSERT INTO scores (username, psnr) VALUES (?, ?)', (username, average_psnr))
                    conn.commit()
                    conn.close()

                    st.success(f"평가 완료! {name}님의 평균 PSNR: {average_psnr:.2f}")

            except Exception as e:
                st.error(f"오류가 발생하여 점수가 저장되지 않았습니다: {e}")

        # 리더보드 표시
        st.subheader("리더보드")
        leaderboard_df = get_leaderboard(db_file)
        st.table(leaderboard_df)

        # 원본 NIfTI 파일 목록 표시 (선택 사항)
        st.subheader("원본 NIfTI 파일 목록")
        st.write("다음은 평가에 사용되는 원본 NIfTI 파일들의 목록입니다:")
        for nii_file in original_nii_files:
            st.write(nii_file)

    elif authentication_status == False:
        st.error('사용자 이름이나 비밀번호가 올바르지 않습니다.')
    elif authentication_status == None:
        st.warning('인증이 필요합니다.')

if __name__ == "__main__":
    main()
