"""Auto-imported via PYTHONPATH; patches colorama before user scripts run."""
import os

if os.environ.get("COMPYCTOR_FORCE_COLOR") != "1":
    pass
else:
    try:
        import colorama.initialise as _ci

        _orig_init = _ci.init

        def _keep_ansi_init(*args, **kwargs):
            kwargs["strip"] = False
            kwargs["convert"] = False
            return _orig_init(*args, **kwargs)

        _ci.init = _keep_ansi_init
        import colorama
        colorama.init = _keep_ansi_init
    except Exception:
        pass
