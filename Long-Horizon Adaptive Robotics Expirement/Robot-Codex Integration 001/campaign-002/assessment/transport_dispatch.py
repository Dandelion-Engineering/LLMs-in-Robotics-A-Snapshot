"""Select a declared transport contract from frozen sources, never observed success."""
from transport_integrity import verify_transport_integrity as verify_v2

V3_METHOD = ('Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/'
             'campaign-002/io-repair/CODEHOST_CHANNEL_TRANSPORT_V3.md')


def verify_transport_integrity(stage_root, frozen, *, owner_kind='model_client'):
    if V3_METHOD in frozen.get('sources', {}):
        from transport_integrity_v3 import verify_transport_integrity
        return verify_transport_integrity(stage_root, frozen, owner_kind=owner_kind)
    return verify_v2(stage_root, frozen, owner_kind=owner_kind)
