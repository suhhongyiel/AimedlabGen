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

    # 데이터베이스 초기화
    db_file = 'scores.db'
    init_db(db_file)

    # 사용자 이름 입력
    username = st.text_input("사용자 이름을 입력하세요")

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

    if uploaded_zip is not None and username:
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
                            uploaded_nii = nib.FileHolder(fileobj=file)
                            generated_image = nib.Nifti1Image.from_file_map({'header': uploaded_nii, 'image': uploaded_nii}).get_fdata()
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

    # 원본 NIfTI 파일 목록 표시 (선택 사항)
    st.subheader("원본 NIfTI 파일 목록")
    st.write("다음은 평가에 사용되는 원본 NIfTI 파일들의 목록입니다:")
    for nii_file in original_nii_files:
        st.write(nii_file)

if __name__ == "__main__":
    main()
