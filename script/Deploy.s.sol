// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../contracts/AgentRegistry.sol";

contract DeployScript is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerKey);

        console.log("Deploying with account:", deployer);
        console.log("Balance:", deployer.balance);

        vm.startBroadcast(deployerKey);

        AgentRegistry registry = new AgentRegistry();
        console.log("AgentRegistry deployed to:", address(registry));

        registry.registerAgent(
            "GoatGuard",
            "http://localhost:3000",
            "ipfs://placeholder-metadata-uri"
        );
        console.log("Agent registered! Token ID: 1");

        vm.stopBroadcast();

        console.log("\n=== Deployment Summary ===");
        console.log("Network: GOAT Testnet3");
        console.log("Contract:", address(registry));
    }
}
