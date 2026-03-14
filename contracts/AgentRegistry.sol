// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";

contract AgentRegistry is ERC721URIStorage {
    uint256 private _nextTokenId;

    struct AgentInfo {
        string name;
        string endpoint;
        uint256 reputationScore;
        uint256 totalJobs;
        bool isActive;
    }

    mapping(uint256 => AgentInfo) public agents;
    mapping(address => uint256) public ownerToAgent;

    event AgentRegistered(uint256 indexed tokenId, string name, address owner);
    event AgentDeactivated(uint256 indexed tokenId);
    event JobCompleted(uint256 indexed tokenId, uint256 newTotal);
    event ReputationUpdated(uint256 indexed tokenId, uint256 newScore);

    constructor() ERC721("GOATAgent", "GAGENT") {}

    function registerAgent(
        string calldata name,
        string calldata endpoint,
        string calldata metadataURI
    ) external returns (uint256) {
        require(ownerToAgent[msg.sender] == 0, "Already registered");

        uint256 tokenId = ++_nextTokenId;
        _mint(msg.sender, tokenId);
        _setTokenURI(tokenId, metadataURI);

        agents[tokenId] = AgentInfo({
            name: name,
            endpoint: endpoint,
            reputationScore: 0,
            totalJobs: 0,
            isActive: true
        });
        ownerToAgent[msg.sender] = tokenId;

        emit AgentRegistered(tokenId, name, msg.sender);
        return tokenId;
    }

    function recordJob(uint256 tokenId) external {
        require(ownerOf(tokenId) == msg.sender, "Not owner");
        agents[tokenId].totalJobs++;
        emit JobCompleted(tokenId, agents[tokenId].totalJobs);
    }

    function updateReputation(uint256 tokenId, uint256 score) external {
        require(ownerOf(tokenId) == msg.sender, "Not owner");
        agents[tokenId].reputationScore = score;
        emit ReputationUpdated(tokenId, score);
    }

    function deactivate(uint256 tokenId) external {
        require(ownerOf(tokenId) == msg.sender, "Not owner");
        agents[tokenId].isActive = false;
        emit AgentDeactivated(tokenId);
    }

    function getAgent(uint256 tokenId) external view returns (AgentInfo memory) {
        require(tokenId > 0 && tokenId <= _nextTokenId, "Invalid token");
        return agents[tokenId];
    }

    function totalAgents() external view returns (uint256) {
        return _nextTokenId;
    }
}
