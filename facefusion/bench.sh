#!/bin/bash

set -u

SOURCE="$HOME/t1.jpg"
TARGET="$HOME/t2.mp4"
OUTDIR="$HOME/facefusion_benchmark"

mkdir -p "$OUTDIR"

run_test() {
    NAME="$1"
    MODEL="$2"
    PIXEL_BOOST="$3"

    echo
    echo "========================================"
    echo " TEST: $NAME"
    echo " MODEL: $MODEL"
    echo " PIXEL BOOST: $PIXEL_BOOST"
    echo "========================================"
    echo

    START=$(date +%s)

    ./run_facefusion_cuda.sh headless-run \
        --processors face_swapper \
        --execution-providers cuda \
        --source-paths "$SOURCE" \
        --target-path "$TARGET" \
        --output-path "$OUTDIR/${NAME}.mp4" \
        --face-swapper-model "$MODEL" \
        --face-swapper-pixel-boost "$PIXEL_BOOST" \
        --workflow-strategy disk \
        --video-memory-strategy strict \
        --execution-thread-count 1 \
        --log-level info

    CODE=$?
    END=$(date +%s)
    TIME=$((END - START))

    echo
    echo "RESULT: $NAME"
    echo "exit code: $CODE"
    echo "time: ${TIME}s"

    if [ "$CODE" -eq 0 ] && [ -f "$OUTDIR/${NAME}.mp4" ]; then
        SIZE=$(du -h "$OUTDIR/${NAME}.mp4" | cut -f1)
        echo "output: $OUTDIR/${NAME}.mp4"
        echo "size: $SIZE"
    else
        echo "FAILED"
    fi

    echo "$NAME|$MODEL|$PIXEL_BOOST|$CODE|${TIME}s" >> "$OUTDIR/results.txt"
}

rm -f "$OUTDIR/results.txt"

run_test "A_hyperswap_1a" "hyperswap_1a_256" "512x512"
run_test "B_hyperswap_1b" "hyperswap_1b_256" "512x512"
run_test "C_hyperswap_1c" "hyperswap_1c_256" "512x512"
run_test "D_uniface" "uniface_256" "512x512"
run_test "E_simswap" "simswap_unofficial_512" "512x512"

echo
echo "========================================"
echo " BENCHMARK FINISHED"
echo "========================================"

cat "$OUTDIR/results.txt"

echo
echo "Videos:"
ls -lh "$OUTDIR"/*.mp4 2>/dev/null
