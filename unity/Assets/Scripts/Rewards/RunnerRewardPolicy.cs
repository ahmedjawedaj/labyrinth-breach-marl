public sealed class RunnerRewardPolicy
{
    private readonly RewardConfig config;

    public RunnerRewardPolicy(RewardConfig rewardConfig)
    {
        config = rewardConfig;
    }

    public float TeamExitSuccessReward => config.RunnerTeamExitSuccess;
    public float BothCapturedPenalty => config.RunnerBothCapturedPenalty;
    public float TaggedPenalty => config.RunnerTaggedPenalty;
    public float SurvivalReward => config.RunnerSurvivalStepBonus;
    public float ExplorationReward => config.RunnerExplorationBonus;
    public float TeamSeparationShaping => config.RunnerTeamSeparationShaping;
    public float WallLoopPenalty => config.RunnerWallLoopPenalty;
    public float EvadeProgressBonus => config.RunnerEvadeProgressBonus;
    public float ThreatApproachPenalty => config.RunnerThreatApproachPenalty;
    public float ThreatRadius => config.RunnerThreatRadius;
    public float ExplorationVisitBonus => config.RunnerExplorationVisitBonus;
    public float OrbitStallPenalty => config.RunnerOrbitStallPenalty;
}
