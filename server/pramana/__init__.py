"""Pramana: a grounded question-answering engine for the IIMB BRSR E1 dataset."""
import os

# The model's matrices are tiny (d=128), so one BLAS thread is fastest. On a
# CPU-quota container (Render free tier) the default of one thread per host core
# makes every matmul wait on throttled threads and costs about a second a query.
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")
