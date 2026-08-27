import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# To make the same figure every time
np.random.seed(42)

fig, axes = plt.subplots(1, 3, figsize=(18, 5))

# =========================
# 1. Anomaly Threshold
# =========================
threshold1 = 0.512

normal = np.random.normal(0.3, 0.07, 500)
attack = np.random.normal(0.7, 0.07, 100)

normal = np.clip(normal, 0, 1)
attack = np.clip(attack, 0, 1)
scores = np.concatenate([normal, attack])

axes[0].hist(normal, bins=40, alpha=0.45, label="Normal")
axes[0].hist(attack, bins=40, alpha=0.45, label="Anomalous")
sns.kdeplot(scores, ax=axes[0], linewidth=2)

axes[0].axvline(threshold1, linestyle="--", linewidth=2, color="red", label="Threshold")
axes[0].set_title("Anomaly Threshold")
axes[0].set_xlabel("Anomaly Score")
axes[0].set_ylabel("Frequency")
axes[0].text(threshold1 + 0.01, axes[0].get_ylim()[1] * 0.9, f"Threshold = {threshold1:.3f}")
axes[0].legend()


# =========================
# 2. Supervised Threshold
# =========================
threshold2 = 0.7

normal_p = np.random.normal(0.3, 0.1, 400)
attack_p = np.random.normal(0.8, 0.1, 200)

normal_p = np.clip(normal_p, 0, 1)
attack_p = np.clip(attack_p, 0, 1)
probs = np.concatenate([normal_p, attack_p])

axes[1].hist(normal_p, bins=40, alpha=0.45, label="Normal")
axes[1].hist(attack_p, bins=40, alpha=0.45, label="Attack")
sns.kdeplot(probs, ax=axes[1], linewidth=2)

axes[1].axvline(threshold2, linestyle="--", linewidth=2, color="red", label="Threshold")
axes[1].set_title("Supervised Threshold (p_attack)")
axes[1].set_xlabel("Attack Probability")
axes[1].set_ylabel("Frequency")
axes[1].text(threshold2 + 0.01, axes[1].get_ylim()[1] * 0.9, f"Threshold = {threshold2:.2f}")
axes[1].legend()


# =========================
# 3. Uncertainty Threshold
# =========================
threshold3 = 0.6

known = np.random.normal(0.3, 0.1, 400)
uncertain = np.random.normal(0.75, 0.1, 150)

known = np.clip(known, 0, 1)
uncertain = np.clip(uncertain, 0, 1)
unc_scores = np.concatenate([known, uncertain])

axes[2].hist(known, bins=40, alpha=0.45, label="Known")
axes[2].hist(uncertain, bins=40, alpha=0.45, label="Uncertain / Zero-day")
sns.kdeplot(unc_scores, ax=axes[2], linewidth=2)

axes[2].axvline(threshold3, linestyle="--", linewidth=2, color="red", label="Threshold")
axes[2].set_title("Uncertainty Threshold")
axes[2].set_xlabel("Uncertainty Score")
axes[2].set_ylabel("Frequency")
axes[2].text(threshold3 + 0.01, axes[2].get_ylim()[1] * 0.9, f"Threshold = {threshold3:.2f}")
axes[2].legend()


plt.suptitle("Multi-Threshold Selection in HAWK-EYE", fontsize=16)
plt.tight_layout()

plt.savefig("reports/all_thresholds_curve.png", dpi=300)
plt.show()