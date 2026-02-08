for N in 0 1 2 3 4 5; do
    ./mqsim -i configs/device/eval/eval_retry_${N}.xml \
            -w configs/workload/eval_ecc_retry_read.xml \
            -o results/ecc_retry/ecc_retry_${N}
done
