import sgtk
import UnityEngine
import UnityEditor

import json
import os
import sys

# Fix-up sys.path so we can access our utils
utils_path = os.path.split(__file__)[0]
utils_path = os.path.join(utils_path, os.pardir, 'utils')
utils_path = os.path.normpath(utils_path)
if utils_path not in sys.path:
    sys.path.append(utils_path)

HookBaseClass = sgtk.get_hook_baseclass()

class UnityActions(HookBaseClass):
    def generate_actions(self, sg_data, actions, ui_area):
        """
        Returns a list of action instances for a particular object.
        The data returned from this hook will be used to populate the 
        actions menu.
    
        The mapping between Shotgun objects and actions are kept in a different place
        (in the configuration) so at the point when this hook is called, the app
        has already established *which* actions are appropriate for this object.
        
        This method needs to return detailed data for those actions, in the form of a list
        of dictionaries, each with name, params, caption and description keys.
        
        The ui_area parameter is a string and indicates where the item is to be shown. 
        
        - If it will be shown in the main browsing area, "main" is passed. 
        - If it will be shown in the details area, "details" is passed.
                
        :param sg_data: Shotgun data dictionary with a set of standard fields.
        :param actions: List of action strings which have been defined in the app configuration.
        :param ui_area: String denoting the UI Area (see above).
        :returns List of dictionaries, each with keys name, params, caption, group and description
        """
        import unity_metadata
        
        app = self.parent
        app.logger.debug("Generate actions called for UI element %s. "
                      "Actions: %s. Shotgun Data: %s" % (ui_area, actions, sg_data))
        
        # get the actions from the base class first
        action_instances = super(UnityActions, self).generate_actions(sg_data, actions, ui_area)

        if "jump_to_frame" not in actions:
            return action_instances

        # The main timeline tag must be defined in the config for jump to 
        # frame to work
        main_timeline_tag = app.settings.get('main_timeline_tag')
        if not main_timeline_tag:
            return action_instances
        
        # Look for metadata
        sg = app.context.sgtk.shotgun
        metadata = unity_metadata.get_metadata_from_entity(sg_data, sg)
        if not metadata:
            return action_instances
        
        # The metadata should point to the current project
        if not unity_metadata.relates_to_current_project(metadata):
            return action_instances
        
        # The metadata should point to a scene that exists in the project
        if not unity_metadata.relates_to_existing_scene(metadata):
            return action_instances
        
        # There should be a frame number
        if not metadata.get('frame_number'):
            return action_instances
        
        # Add the main timeline tag to the passed params
        metadata['main_timeline_tag'] = main_timeline_tag
        
        action_instances.append( 
            {"name": "jump_to_frame", 
              "params": metadata,
              "group": "Jump to Frame",
              "caption": "Jump to Frame",
              "description": "Opens the associated Unity scene and scrubs to the associated frame."} )

        return action_instances

    def execute_action(self, name, params, sg_data):
        """
        Execute a given action. The data sent to this be method will
        represent one of the actions enumerated by the generate_actions method.
        
        :param name: Action name string representing one of the items returned by generate_actions.
        :param params: Params data, as specified by generate_actions.
        :param sg_data: Shotgun data dictionary
        :returns: No return value expected.
        """
        app = self.parent
        app.logger.debug("Execute action called for action %s. "
                      "Parameters: %s. Shotgun Data: %s" % (name, params, sg_data))
        
        if name == "jump_to_frame":
            
            # Open the scene
            metadata = params
            frame_number = int(metadata['frame_number'])
            UnityEditor.SceneManagement.EditorSceneManager.OpenScene(metadata.get('scene_path'))

            # Set the current time            
            UnityEditor.EditorApplication.ExecuteMenuItem("Window/Sequencing/Timeline")
        
            # Find the right director
            main_director = None
            game_objects = UnityEngine.GameObject.FindGameObjectsWithTag(params['main_timeline_tag'])
            if game_objects:
                main_director = game_objects[0].GetComponent(UnityEngine.Playables.PlayableDirector)

            if main_director:
                try:
                    # focus on the PlayableDirector in the Timeline window
                    UnityEditor.Selection.activeObject = main_director
                    
                    timeline = main_director.playableAsset
                    if timeline:
                        fps = timeline.editorSettings.fps
                        main_director.time = frame_number / fps
                    else:
                        app.logger.error('Shotgun is unable to jump to frame: The "{}" PlayableDirector does not have a valid Playable Asset assigned.'.format(game_objects[0].name))

                    
                except Exception as e:
                    app.logger.error('Unable to Jump to Frame: ' + str(e))
            else:
                app.logger.error('Shotgun is unable to jump to frame: please choose a PlayableDirector and tag it with "{}".'.format(params['main_timeline_tag']))
        else:
            super(UnityActions, self).execute_action(name, params, sg_data)
