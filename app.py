# app.py

import streamlit as st
import os
import numpy as np
import pandas as pd
from PIL import Image
from math import log10, sqrt
import zipfile
import io
import sqlite3

# 데이터베이스 초기화 함수
def init_db(db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            psnr REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# 점수 저장 함수
def save_score(db_file, username, psnr):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO scores (username, psnr) VALUES (?, ?)
    ''', (username, psnr))
    conn.commit()
    conn.close()

# 리더보드 가져오기 함수
def get_leaderboard(db_file):
    conn = sqlite3.connect(db_file)
    df = pd.read_sql_query("SELECT username, psnr FROM scores ORDER BY psnr DESC", conn)
    conn.close()
    return df

# PSNR 계산 함수
def calculate_psnr(original, generated):
    original = np.array(original).astype(np.float32)
    generated = np.array(generated).astype(np.float32)
    mse = np.mean((original - generated) ** 2)
    if mse == 0:
        return float('inf')
    max_pixel = 255.0
    psnr = 20 * log10(max_pixel / sqrt(mse))
    return psnr

# 메인 함수
def main():
    st.title("이미지 제출 및 PSNR 평가")
    st.write("생성한 이미지를 제출하여 원본 이미지와의 PSNR 점수를 확인하세요.")

    # 데이터베이스 초기화
    db_file = 'scores.db'
    init_db(db_file)

    # 사용자 이름 입력
    username = st.text_input("사용자 이름을 입력하세요")

    # 이미지 파일 업로드
    uploaded_zip = st.file_uploader("생성한 이미지들을 압축하여 업로드하세요 (ZIP 파일)", type=["zip"])

    # 원본 이미지 로드
    original_image_folder = 'test_images'  # 공개된 테스트 이미지 폴더
    if not os.path.exists(original_image_folder):
        st.error(f"원본 이미지 폴더 '{original_image_folder}'가 존재하지 않습니다.")
        return
    original_image_files = [f for f in os.listdir(original_image_folder) if f.endswith(('.png', '.jpg', '.jpeg'))]
    if not original_image_files:
        st.error("원본 이미지가 존재하지 않습니다.")
        return

    if uploaded_zip is not None and username:
        try:
            # 업로드된 ZIP 파일 읽기
            with zipfile.ZipFile(uploaded_zip) as zip_ref:
                uploaded_files = zip_ref.namelist()
                if len(uploaded_files) != len(original_image_files):
                    st.error(f"이미지 개수가 일치하지 않습니다. 원본 이미지 개수: {len(original_image_files)}")
                    return

                psnr_values = []

                for original_file in original_image_files:
                    # 원본 이미지 로드
                    original_image_path = os.path.join(original_image_folder, original_file)
                    original_image = Image.open(original_image_path).convert('RGB')

                    # 대응되는 업로드된 이미지 찾기
                    if original_file in uploaded_files:
                        with zip_ref.open(original_file) as file:
                            generated_image = Image.open(file).convert('RGB')
                    else:
                        st.error(f"'{original_file}' 파일이 업로드된 ZIP에 포함되어 있지 않습니다.")
                        return

                    # PSNR 계산
                    psnr = calculate_psnr(original_image, generated_image)
                    psnr_values.append(psnr)

                # 평균 PSNR 계산
                average_psnr = sum(psnr_values) / len(psnr_values)

                # 점수 저장
                save_score(db_file, username, average_psnr)

                st.success(f"평가 완료! {username}님의 평균 PSNR: {average_psnr:.2f}")

            # 업로드된 파일 삭제 (메모리에서 처리되므로 생략 가능)

        except Exception as e:
            st.error(f"오류가 발생하여 점수가 저장되지 않았습니다: {e}")

    elif uploaded_zip is not None and not username:
        st.warning("사용자 이름을 입력하세요.")

    # 리더보드 표시
    st.subheader("리더보드")
    leaderboard_df = get_leaderboard(db_file)
    st.table(leaderboard_df)

    # 원본 이미지 표시 (선택 사항)
    st.subheader("원본 이미지")
    cols = st.columns(5)
    for idx, img_file in enumerate(original_image_files):
        img_path = os.path.join(original_image_folder, img_file)
        image = Image.open(img_path)
        cols[idx % 5].image(image, caption=img_file, use_column_width=True)

if __name__ == "__main__":
    main()
