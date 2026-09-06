#!/bin/bash
# ─────────────────────────────────────────────────────────────
# ONNX → RDK X5 BPU .bin  (D-Robotics OpenExplorer(OE) docker 안에서 실행)
#
# 1) PC(x64, Docker Desktop/리눅스)에서 media 폴더를 통째로 마운트해 OE docker 진입:
#    docker run -it --rm --platform linux/amd64 -v /path/to/media:/work -w /work/14_export_BPU \
#        openexplorer/ai_toolchain_ubuntu_20_x5_cpu:v1.2.8 bash convert.sh
# 2) → out/<모델>/<모델>.bin 생성 후 ../15_rdk_x5_runtime/models/ 로 복사 (보드에 15_rdk_x5_runtime 통째로 배포)
# 전제: export_onnx.py(onnx/*.onnx, YOLO 는 분리 헤드) · calib_prep.py(calib/*) 를 PC 에서 먼저 실행.
# 출력: 모델마다 배너로 구분하고, checker/makertbin 로그는 6칸 들여쓰기 → 어느 모델 블록인지 한눈에 보이게.
# ─────────────────────────────────────────────────────────────
set -e
set -o pipefail                       # 들여쓰기용 파이프(sed)를 써도 hb_mapper 실패 시 즉시 중단
cd "$(dirname "$0")"
DST="../15_rdk_x5_runtime/models"; [ -d "$DST" ] || DST="./bin"; mkdir -p "$DST"
IND='      '                          # hb_mapper 로그 들여쓰기(6칸)

banner() {                            # 모델 구분 배너
  echo; echo; echo
  echo "################################################################################"
  echo "#####"
  echo "#####   모델 [$1/3] : $2      (onnx/$2.onnx → $DST/$2.bin)"
  echo "#####"
  echo "################################################################################"
  echo
}

i=0
for m in detection pose face_state; do
  i=$((i + 1))
  [ -f "onnx/$m.onnx" ] || { echo "[에러] onnx/$m.onnx 없음 — export_onnx.py 먼저"; exit 1; }
  banner "$i" "$m"

  echo "    ── [$m] 1/2 checker : BPU 지원 op 점검 ────────────────────────────"
  echo
  hb_mapper checker --model-type onnx --march bayes-e --model "onnx/$m.onnx" 2>&1 | sed "s/^/$IND/"
  echo
  echo "    ── [$m] 2/2 makertbin : 캘리브레이션 → INT8 양자화 → 컴파일 ───────"
  echo
  hb_mapper makertbin --config "$m.yaml" --model-type onnx 2>&1 | sed "s/^/$IND/"
  echo
  cp "out/$m/$m.bin" "$DST/$m.bin"
  echo "    ✔ [$m] 완료 → $DST/$m.bin  ($(du -h "$DST/$m.bin" | cut -f1))"
done

echo; echo
echo "################################################################################"
echo "#####   전체 완료: $DST 에 detection.bin / pose.bin / face_state.bin"
echo "#####   보드: 15_rdk_x5_runtime 폴더 복사(models/ 의 .bin + *_info.json 포함) → .env BACKEND=bpu → python3 2_run_test.py"
echo "################################################################################"
