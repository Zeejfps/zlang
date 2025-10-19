using ParserModule.Nodes;
using ParserModule.Visitors;

namespace SemanticAnalysisModule;

public sealed class ReturnsOnAllPathAnalyzer : IStatementNodeVisitor
{
    public TypeNode? ExpectedReturnType { get; init; }
    
    public bool Result { get; private set; }

    private bool ReturnsOnAllPaths(StatementNode statement)
    {
        statement.Accept(this);
        return Result;
    }

    public void VisitIfStatementNode(IfStatementNode ifStatement)
    {
        var thenReturns = ReturnsOnAllPaths(ifStatement.ThenBranch);
        var elseReturns = ifStatement.ElseBranch != null && ReturnsOnAllPaths(ifStatement.ElseBranch);
        Result = thenReturns && elseReturns;
    }

    public void VisitBlockStatement(BlockStatementNode blockStatement)
    {
        Result = blockStatement
            .Statements
            .Any(ReturnsOnAllPaths);
    }

    public void VisitReturnStatementNode(ReturnStatementNode returnStatement)
    {
        Result = ExpectedReturnType == returnStatement.InferredType;
    }

    public void VisitForStatement(ForStatemetNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitVarDeclaration(VarDeclarationStatementNode node)
    {
        Result = false;
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