"""Prospective matched revision authorized October 7, 2026 at 11:50 PDT."""
CONFIG=dict(normal_work_s=360,throw_work_s=600,reserve_s=3600,model_wall_s=7200,
            recovery_policy='verified-boundary-branch-1',timing_policy='simulation-and-monotonic-epochs-1')
REVISION='APARTMENT-v2-reliability-frozen'
PREFIX='APARTMENT-v2'
RUNTIME=('common.py','content_store.py','journal_reader.py','journal_service.py','native_runtime.py','native_stream.py',
         'structured_errors.py','transport.py','frame_digest.py','flow_control.py','h2_runtime.py','h2_readback.py',
         'transport_inside.py','guest_entry.py','run.py','scene.py','world.py','controller.py','recording.py','recovery.py',
         'schedule.py','deployment.py','broker.py','guest_probe.py','image_sensor.py','robot_client.py','viewer.py','viewer.html','revision_config.py')
