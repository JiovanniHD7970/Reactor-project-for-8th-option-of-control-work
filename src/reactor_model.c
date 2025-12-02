#define EXPORT __declspec(dllexport)

EXPORT double compute_CB(double Q, double CA_in, double k1, double k2, double Vr) {
    return (2.0 * k1 * Vr * Q * CA_in) / ((Q + k1 * Vr) * (Q + k2 * Vr));
}