using System;
using System.Collections.Generic;
using System.Reflection;
using HarmonyLib;
using UnityEngine;

namespace com.github.lhervier.ksp.fix.constructioncollider
{
    /// <summary>
    /// Keeps a part edited in EVA construction mode from staying a trigger once released. While a part is edited,
    /// the construction mode turns its colliders into triggers, after recording each one's state, and puts that
    /// state back when the part is released. On stock, switching between the Move and Rotate tools with the part
    /// still selected records the colliders again while they are triggers: the part is then released as a trigger
    /// and no longer collides with anything, the ground included, until the game is loaded again. Before each
    /// recording, the colliders of the previous one are put back as they were.
    /// </summary>
    internal static class CollidersBackBeforeRecording
    {
        // EVAConstructionModeEditor.FetchColliders fills this list; ToggleCollidersTrigger(false) puts it back.
        private static readonly FieldInfo Recorded =
            AccessTools.Field(typeof(EVAConstructionModeEditor), "selectedPartColliders");
        private static readonly MethodInfo FetchColliders =
            AccessTools.Method(typeof(EVAConstructionModeEditor), "FetchColliders");
        private static readonly MethodInfo ToggleCollidersTrigger =
            AccessTools.Method(typeof(EVAConstructionModeEditor), "ToggleCollidersTrigger");

        /// <summary>Patches the construction mode's recording of the colliders.</summary>
        /// <exception cref="MissingMemberException">The construction mode does not have the members patched.</exception>
        public static void Install(Harmony harmony)
        {
            if (Recorded == null || FetchColliders == null || ToggleCollidersTrigger == null)
            {
                throw new MissingMemberException("EVAConstructionModeEditor.selectedPartColliders, .FetchColliders " +
                    "or .ToggleCollidersTrigger");
            }
            harmony.Patch(FetchColliders,
                prefix: new HarmonyMethod(typeof(CollidersBackBeforeRecording), nameof(FetchCollidersPrefix)));
        }

        /// <summary>Puts the colliders of the previous recording back as they were, before the new one.</summary>
        private static void FetchCollidersPrefix(EVAConstructionModeEditor __instance)
        {
            List<EVAConstructionModeEditor.SelectedPartCollider> recorded =
                Recorded.GetValue(__instance) as List<EVAConstructionModeEditor.SelectedPartCollider>;
            if (recorded == null || recorded.Count == 0)
            {
                return;
            }
            // Counted for the log only: the colliders still triggers that were not when recorded. None when the
            // stock code already put them back, as it does when the selection changes.
            int stillTriggers = 0;
            Part part = null;
            foreach (EVAConstructionModeEditor.SelectedPartCollider c in recorded)
            {
                if (c != null && c.collider != null && c.collider.isTrigger && !c.isTrigger)
                {
                    stillTriggers++;
                    part = part ?? FlightGlobals.GetPartUpwardsCached(c.collider.gameObject);
                }
            }
            ToggleCollidersTrigger.Invoke(__instance, new object[] { false });
            if (stillTriggers > 0)
            {
                Log.Debug($"{stillTriggers} collider(s) of {(part != null ? part.partInfo.title : "a part")} put back " +
                    "before the construction mode records them again");
            }
        }
    }
}
