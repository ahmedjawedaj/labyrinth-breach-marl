public static class RewardEvent
{
    public const string CaptureEvent = "capture_event";
    public const string CaptureReward = "capture_reward";
    public const string CapturePenalty = "capture_penalty";
    public const string SurvivalReward = "survival_reward";
    public const string ExplorationBonus = "exploration_bonus";
    public const string TimeoutPenalty = "timeout_penalty";
    public const string EpisodeWin = "episode_win";
    public const string EpisodeLoss = "episode_loss";
    public const string TrapPincer = "trap_pincer";
    public const string TrapEnclosure = "trap_enclosure";
    public const string TrapDeadEndForcing = "trap_dead_end_forcing";
    public const string TrapExitDenial = "trap_exit_denial";
    public const string TrapCorridorControl = "trap_corridor_control";
    public const string ClusterPenalty = "cluster_penalty";
    public const string ExitGuardShaping = "exit_guard_shaping";
    public const string TeamSeparationShaping = "team_separation_shaping";
    public const string StepPenalty = "step_penalty";

    public static string CategoryFor(string eventName)
    {
        switch (eventName)
        {
            case EpisodeWin:
            case EpisodeLoss:
                return "terminal";
            case CaptureReward:
            case CapturePenalty:
                return "capture";
            case TrapPincer:
            case TrapEnclosure:
            case TrapDeadEndForcing:
            case TrapExitDenial:
            case TrapCorridorControl:
                return "trap";
            case TimeoutPenalty:
            case ClusterPenalty:
            case StepPenalty:
                return "penalty";
            case SurvivalReward:
            case ExplorationBonus:
            case ExitGuardShaping:
            case TeamSeparationShaping:
                return "shaping";
            default:
                return "event";
        }
    }

    public static bool CanApplyToInactiveAgent(string eventName)
    {
        return eventName == CapturePenalty
            || eventName == EpisodeWin
            || eventName == EpisodeLoss
            || eventName == TimeoutPenalty;
    }
}
