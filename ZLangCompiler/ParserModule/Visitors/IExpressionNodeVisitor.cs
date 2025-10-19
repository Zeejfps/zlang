using ParserModule.Nodes;
using ParserModule.Nodes.Expressions;

namespace ParserModule.Visitors;

public interface IExpressionNodeVisitor
{
    void VisitBinary(BinaryExpressionNode node);
    void VisitUnary(UnaryExpressionNode node);
    void VisitLiteralInteger(LiteralIntegerExpressionNode node);
    void VisitLiteralBool(LiteralBoolExpressionNode node);
    void VisitQualifiedIdentifier(QualifiedIdentifierExpressionNode node);
    void VisitFunctionCall(FunctionCallNode node);
}