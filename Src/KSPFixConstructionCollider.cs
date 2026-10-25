using System;
using HarmonyLib;
using UnityEngine;

namespace com.github.lhervier.ksp.fix.constructioncollider
{
    /// <summary>
    /// Installs the fix the settings turn on, once, when KSP starts: from then on, a part edited in EVA construction
    /// mode collides again once released, even when it was switched between the Move and Rotate tools while
    /// selected.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.Instantly, true)]
    public class KSPFixConstructionCollider : MonoBehaviour
    {
        private const string HarmonyId = "com.github.lhervier.ksp.fix.constructioncollider";

        private void Start()
        {
            Settings.Load();
            Log.Info($"Version {typeof(KSPFixConstructionCollider).Assembly.GetName().Version}, " +
                $"releasedPartCollides {Settings.ReleasedPartCollides}, log level {Log.Level}");
            if (!Settings.ReleasedPartCollides)
            {
                return;
            }
            try
            {
                CollidersBackBeforeRecording.Install(new Harmony(HarmonyId));
                Log.Info("Released part collides fix installed");
            }
            catch (Exception e)
            {
                Log.Error("Could not install the released part collides fix, a part switched between the Move and " +
                    $"Rotate tools stays a trigger as on stock: {e}");
            }
        }
    }
}
