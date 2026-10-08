typedef struct{ double hi; double lo; } DoubleLength;

static DoubleLength
dl_fast_sum(double a, double b)
{
    /* Algorithm 1.1. Compensated summation of two floating-point numbers. */
    assert(fabs(a) >= fabs(b));
    double x = a + b;
    double y = (a - x) + b;
    return (DoubleLength) {x, y};
}

static DoubleLength
dl_sum(double a, double b)
{
    /* Algorithm 3.1 Error-free transformation of the sum */
    double x = a + b;
    double z = x - a;
    double y = (a - (x - z)) + (b - z);
    return (DoubleLength) {x, y};
}


static DoubleLength
dl_mul(double x, double y)
{
    /* Algorithm 3.5. Error-free transformation of a product */
    double z = x * y;
    double zz = fma(x, y, -z);
    return (DoubleLength) {z, zz};
}

static inline double
vector_norm(Py_ssize_t n, double *vec, double max, int found_nan)
{
    double x, h, scale, csum = 1.0, frac1 = 0.0, frac2 = 0.0;
    DoubleLength pr, sm;
    int max_e;
    Py_ssize_t i;

    if (isinf(max)) {
        return max;
    }
    if (found_nan) {
        return Py_NAN;
    }
    if (max == 0.0 || n <= 1) {
        return max;
    }
    frexp(max, &max_e);
    if (max_e < -1023) {
        /* When max_e < -1023, ldexp(1.0, -max_e) would overflow. */
        for (i=0 ; i < n ; i++) {
            vec[i] /= DBL_MIN;          // convert subnormals to normals
        }
        return DBL_MIN * vector_norm(n, vec, max / DBL_MIN, found_nan);
    }
    scale = ldexp(1.0, -max_e);
    assert(max * scale >= 0.5);
    assert(max * scale < 1.0);
    for (i=0 ; i < n ; i++) {
        x = vec[i];
        assert(isfinite(x) && fabs(x) <= max);
        x *= scale;                     // lossless scaling
        assert(fabs(x) < 1.0);
        pr = dl_mul(x, x);              // lossless squaring
        assert(pr.hi <= 1.0);
        sm = dl_fast_sum(csum, pr.hi);  // lossless addition
        csum = sm.hi;
        frac1 += pr.lo;                 // lossy addition
        frac2 += sm.lo;                 // lossy addition
    }
    h = sqrt(csum - 1.0 + (frac1 + frac2));
    pr = dl_mul(-h, h);
    sm = dl_fast_sum(csum, pr.hi);
    csum = sm.hi;
    frac1 += pr.lo;
    frac2 += sm.lo;
    x = csum - 1.0 + (frac1 + frac2);
    h +=  x / (2.0 * h);                 // differential correction
    return h / scale;
}

static double norm_two(double x,double y) {
    double vec[2]={fabs(x),fabs(y)},maximum=0.;
    for (int i=0;i<2;++i) if (vec[i]>maximum) maximum=vec[i];
    return vector_norm(2,vec,maximum,isnan(x) || isnan(y));
}
