using ParserModule.Nodes;
using ParserModule.Visitors;

namespace SemanticAnalysisModule;

public sealed class FunctionAnalyzer
{
    private readonly string _moduleIdentifier;

    public FunctionAnalyzer(string moduleIdentifier)
    {
        _moduleIdentifier = moduleIdentifier;
    }

    public void Analyze(FunctionDefinitionNode functionDefinition)
    {
        var signature = functionDefinition.Signature;
        signature.Identifier = $"{_moduleIdentifier}.{signature.Identifier}";
        
        var body = functionDefinition.Body;
        if (body.Statements.Last() is not ReturnStatementNode)
        {
            body.Statements.Add(new ReturnStatementNode());
        }
    }

    public bool AnalyzeReturnsOnAllPaths(FunctionDefinitionNode functionDefinition)
    {
        var statementAnalyzer = new StatementAnalyzer();
        var statements = functionDefinition.Body.Statements;
        foreach (var statement in statements)
        {
            var result = statementAnalyzer.AnalyzeReturnsOnAllPaths(statement);
            if (!result)
            {
                return false;
            }
        }
        return true;
    }
}

public sealed class StatementAnalyzer
{
    public bool AnalyzeReturnsOnAllPaths(StatementNode statement)
    {
        return true;
    }
}