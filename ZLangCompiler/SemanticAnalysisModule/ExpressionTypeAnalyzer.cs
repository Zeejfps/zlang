using ParserModule.Nodes;
using ParserModule.Nodes.Expressions;
using ParserModule.Visitors;

namespace SemanticAnalysisModule;

public sealed class ExpressionTypeAnalyzer : IExpressionNodeVisitor
{
    private TypeNode? Result { get; set; }

    public TypeNode? InferType(ExpressionNode expression)
    {
        expression.Accept(this);
        return Result;
    }
    
    public void VisitBinary(BinaryExpressionNode binaryExpression)
    {
        var leftType = InferType(binaryExpression.Left);
        var rightType = InferType(binaryExpression.Right);
        Result = leftType;
    }

    public void VisitUnary(UnaryExpressionNode node)
    {
        Result = InferType(node);
    }

    public void VisitLiteralInteger(LiteralIntegerExpressionNode node)
    {
        Result = new NamedTypeNode
        {
            Identifier = "u32"
        };
    }

    public void VisitLiteralBool(LiteralBoolExpressionNode node)
    {
        Result = new NamedTypeNode
        {
            Identifier = "bool"
        };
    }

    public void VisitQualifiedIdentifier(QualifiedIdentifierExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitFunctionCall(FunctionCallNode node)
    {
        throw new NotImplementedException();
    }
}