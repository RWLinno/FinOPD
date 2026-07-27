import torch

from finvl.factors.router import FactorRouter
from finvl.self_evolution.grpo_lite.router_update import GRPOLiteUpdater


def test_online_router_update_uses_recorded_topk_actions():
    torch.manual_seed(7)
    router = FactorRouter(
        geometry_dim=3,
        regime_dim=2,
        num_factors=5,
        hidden_dim=8,
        top_k=2,
    )
    features = torch.tensor(
        [[1.0, 0.0, -1.0], [0.5, -0.5, 1.0], [-1.0, 1.0, 0.0]]
    )
    regimes = torch.tensor([[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]])
    selections = torch.tensor(
        [[1.0, 1.0, 0.0, 0.0, 0.0],
         [0.0, 0.0, 1.0, 1.0, 0.0],
         [1.0, 0.0, 0.0, 0.0, 1.0]]
    )
    utilities = torch.tensor([1.0, -0.5, 0.25])
    before = {key: value.detach().clone() for key, value in router.state_dict().items()}

    metrics = GRPOLiteUpdater(lr=1e-3).update(
        router,
        features,
        regimes,
        utilities,
        selection_mask=selections,
    )

    assert all(torch.isfinite(torch.tensor(value)) for value in metrics.values())
    assert any(
        not torch.equal(before[key], value)
        for key, value in router.state_dict().items()
    )
