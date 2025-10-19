using ParserModule.Nodes;
using ParserModule.Visitors;

namespace SemanticAnalysisModule;

public sealed class ReturnsOnAllPathAnalyzer : IStatementNodeVisitor
{
    public TypeNode? ExpectedReturnType { get; init; }
    
    public bool Result { get; private set; }

    public static bool ReturnsOnAllPaths(StatementNode statement, TypeNode? expectedReturnType)
    {
        if (statement is ReturnStatementNode returnStatementNode)
        {
            return expectedReturnType == returnStatementNode.InferredType;
        }

        if (statement is BlockStatementNode blockStatement)
        {
            return blockStatement
                .Statements
                .Any(stmt => ReturnsOnAllPaths(stmt, expectedReturnType));
        }

        if (statement is IfStatementNode ifStatement)
        {
            var thenReturns = ReturnsOnAllPaths(ifStatement.ThenBranch, expectedReturnType);
            var elseReturns = ifStatement.ElseBranch != null && ReturnsOnAllPaths(ifStatement.ElseBranch, expectedReturnType);
            return thenReturns && elseReturns;
        }

        return false;
    }

    public void VisitIfStatementNode(IfStatementNode ifStatement)
    {
        var expectedReturnType = ExpectedReturnType;
        var thenReturns = ReturnsOnAllPaths(ifStatement.ThenBranch, expectedReturnType);
        var elseReturns = true;
        if (ifStatement.ElseBranch != null)
        {
            elseReturns = ReturnsOnAllPaths(ifStatement.ElseBranch, expectedReturnType);
        }

        Result = thenReturns && elseReturns;
    }

    public void VisitBlockStatement(BlockStatementNode blockStatement)
    {
        Result = blockStatement
            .Statements
            .Any(stmt => ReturnsOnAllPaths(stmt, ExpectedReturnType));
    }

    public void VisitReturnStatementNode(ReturnStatementNode returnStatement)
    {
        Result = ExpectedReturnType == returnStatement.InferredType;
    }

    public void VisitForStatement(ForStatemetNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitVarDefinition(VarDefinitionStatementNode node)
    {
        
    }

    public void VisitVarDeclaration(VarDeclarationStatementNode node)
    {
    }

    public void VisitVarAssignment(VarAssignmentStatementNode node)
    {
    }

    public void VisitWhileStatement(WhileStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitExpressionStatement(ExpressionStatement node)
    {
    }
}