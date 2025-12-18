import sys
from unittest.mock import MagicMock, patch
from argparse import Namespace

# Mocking modules to avoid import errors if environment is not perfect
# (though in this workspace likely it is fine, but better safe)
# epaper.service.main imports
# from jetson.common.service_runner ...
# from ..backends.factory ...
# from ..core import modes
# from ..core.display import DisplayManager
# from ..scenes ...

# We will let the imports happen, assuming the file exists. 
# If imports fail, we'll see.

try:
    from epaper.service.main import EpaperService
except ImportError:
    # Attempt to add current dir to path if needed, but workspace root should be in path?
    sys.path.append("/workspace")
    from epaper.service.main import EpaperService

def test_double_start():
    print("Starting reproduction test...")
    with patch('epaper.service.main.DisplayManager') as MockDisplayManager, \
         patch('epaper.service.main.SCENE_MAP') as MockSceneMap:
        
        # Setup the mock instance
        mock_manager_instance = MockDisplayManager.return_value
        
        # Setup mock scene
        mock_scene = MagicMock()
        mock_scene.frames.return_value = [] # Empty frames so loop finishes
        
        mock_factory = MagicMock(return_value=mock_scene)
        MockSceneMap.get.return_value = mock_factory
        
        # Setup args
        args = Namespace(shutdown=False)
        config = {"backend": "fake", "scene": "test_scene"}
        
        # Instantiate service
        service = EpaperService(config, args)
        
        # Run
        service.run()
        
        print(f"DisplayManager.start called {mock_manager_instance.start.call_count} times")
        
        if mock_manager_instance.start.call_count == 2:
            print("ISSUE REPRODUCED: start() called twice.")
        else:
            print(f"Issue not reproduced. start() called {mock_manager_instance.start.call_count} times.")

if __name__ == "__main__":
    test_double_start()
