#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 3-1단계 — PC 에서 같은 실시간 스트림을 torch(float) 모델로 3_gui_test 와 **똑같이** 창에 시각화
#   cd D:\Code\Monitoring\IoT-Monitoring\media\15_rdk_x5_runtime
#   ..\.venv\Scripts\python.exe 3_1_pc_live_test.py                    # .env STREAM_URL, 창 1280x720
#   ..\.venv\Scripts\python.exe 3_1_pc_live_test.py --win 1600x900 --vis-conf 0.2
#   보드(BPU, INT8 .bin) 화면과 나란히 비교:
#     PC 는 잡는데 보드만 못 잡음 → .bin 입력형식/양자화 문제(보드 로그의 [vision_bpu] 입력 속성·det max 확인)
#     PC 도 못 잡음            → 모델/장면 문제(조명·각도·데이터 부족)
#   HUD 의 age/rx 로 PC 쪽 지연도 확인. 키: space 일시정지 · q/ESC 종료
# ─────────────────────────────────────────────────────────────
r"""3_gui_test.py 를 그대로 import 해 실행하되 BACKEND=torch 를 강제하고 기본 소스를 .env 의 STREAM_URL(실시간)로 둔다.
코드 복제 없음 — 오버레이·HUD·키 동작은 3_gui_test 와 동일(창 모드)."""
import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ["BACKEND"] = "torch"                         # PC 강제(.env 의 BACKEND 무시 — 실제 env 가 우선)


def main() -> int:
    spec = importlib.util.spec_from_file_location("gui_test", HERE / "3_gui_test.py")
    G = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(G)
    if "--src" not in sys.argv:                          # 기본: 실시간 스트림
        sys.argv += ["--src", G.M.STREAM_URL]
    if "--win" not in sys.argv:
        sys.argv += ["--win", "1280x720"]
    print(f"[3_1_pc_live_test] PC torch(float) 백엔드로 실시간 확인 — 보드(BPU) 화면과 비교하세요. src={G.M.STREAM_URL}")
    return G.main()


if __name__ == "__main__":
    raise SystemExit(main())
