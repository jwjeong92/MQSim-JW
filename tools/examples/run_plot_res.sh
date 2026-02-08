#!/bin/bash
cd results &&
# 경로 및 스크립트 설정
PYTHON_SCRIPT="plot_results.py"

# 해당 디렉토리의 모든 xml 파일 순회
for xml_file in *.xml; do
    # 파일이 실제로 존재하는지 확인 (xml 파일이 하나도 없을 경우 에러 방지)
    if [ -f "$xml_file" ]; then
        echo "Processing: $xml_file"
        python3 "$PYTHON_SCRIPT" "$xml_file"
    else
        echo "No XML files found in $SEARCH_DIR"
    fi
done