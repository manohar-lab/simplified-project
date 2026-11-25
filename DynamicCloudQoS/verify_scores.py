"""Quick verification of QoS scores against research paper values."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from service_registry import get_baseline_services
from qos_evaluator import evaluate_service, DEFAULT_WEIGHTS
from recommendation_engine import recommend

svcs = get_baseline_services("Compute")
svc = svcs[0]
score, norms = evaluate_service(svc)

print(f"Service: {svc.name} ({svc.service_id})")
print(f"QoS Score: {score}")
print(f"Normalized latency:      {norms['latency']:.4f}")
print(f"Normalized cost:         {norms['cost']:.4f}")
print(f"Normalized availability: {norms['availability']:.4f}")
print(f"Normalized reliability:  {norms['reliability']:.4f}")
print()

r = recommend(svcs, "Compute")
print(f"Selected: {r.selected_service.name} (score={r.selected_score})")
print(f"Runner-up: {r.runner_up.name} (score={r.runner_up_score}, margin={r.score_margin})")
print()

print("All service scores:")
for svc_item, sc, nm in r.ranking:
    print(f"  {svc_item.service_id} {svc_item.name:25s} -> {sc:.4f}")
