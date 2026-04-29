public sealed class SentinelRewardPolicy
{
    private readonly RewardConfig config;

    public SentinelRewardPolicy(RewardConfig rewardConfig)
    {
        config = rewardConfig;
    }

    public float CaptureReward => config.SentinelIndividualCaptureBonus;
    public float TeamFullCaptureReward => config.SentinelTeamFullCapture;
    public float TimeoutOrEscapePenalty => config.SentinelTimeoutOrEscapePenalty;
    public float EncirclementReward => config.SentinelEncirclementBonus;
    public float ClusterPenalty => config.SentinelClusterPenalty;
    public float ExitGuardShaping => config.SentinelExitGuardShaping;
    public float StepPenalty => config.SentinelStepPenalty;
    public float PincerReward => config.TrapPincerFormationBonus;
    public float EnclosureReward => config.TrapOppositeSideEnclosureBonus;
    public float DeadEndForcingReward => config.TrapDeadEndForcingBonus;
    public float ExitDenialReward => config.TrapExitDenialPressureBonus;
    public float CorridorControlReward => config.TrapCorridorControlBonus;
}
